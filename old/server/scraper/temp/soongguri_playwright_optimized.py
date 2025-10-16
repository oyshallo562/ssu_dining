# soongguri_playwright.py

import json
import re
from datetime import datetime
from dateutil import tz
from playwright.sync_api import sync_playwright
from pathlib import Path

# 식당 정보
TARGETS = [
    {"key": "students", "label": "학생식당", "building": "학생회관", "location_detail": "2층"},
    {"key": "dodam", "label": "숭실도담식당", "building": "숭실도담", "location_detail": "생활관 1층"},
    {"key": "foodcourt", "label": "푸드코트", "building": "신양관", "location_detail": "1층"},
]

MOBILE_URL = "https://soongguri.com/m/"
OUT_PATH = Path(__file__).resolve().parent / "data" / "menus.json"

def _now_kr_iso():
    KST = tz.gettz("Asia/Seoul")
    return datetime.now(tz=KST).isoformat(timespec="seconds")

def parse_corner_text(text: str) -> dict:
    """단일 코너의 텍스트를 파싱하여 메뉴 정보를 추출합니다."""
    lines = text.strip().split('\n')

    corner_name = None
    menu_name = None
    menu_name_en = None
    rating = None
    side_items = []
    current_meal = "중식"  # 기본값

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 코너명 추출 [뚝배기코너]
        if line.startswith('[') and line.endswith(']'):
            corner_name = line[1:-1]

        # 식사 시간대 감지
        elif '아침' in line or '조식' in line or '천원의아침밥' in corner_name:
            current_meal = "조식"

        # 별점과 메뉴명 추출 (★로 시작)
        elif '★' in line and '-' in line:
            # "★ 뚝배기설렁탕 - 5.0" 형식
            parts = line.split('★')[1].strip()
            if '-' in parts:
                name_part, rating_part = parts.rsplit('-', 1)
                menu_name = name_part.strip()
                try:
                    rating = float(rating_part.strip())
                except:
                    rating = None

        # 영문 메뉴명 (대문자로 시작하고 여러 단어)
        elif line and len(line) > 5 and line[0].isupper() and ' ' in line and not line.startswith('*'):
            # 영문인지 확인 (알파벳 비율이 높은지)
            alpha_count = sum(1 for c in line if c.isalpha())
            if alpha_count / len(line) > 0.5:
                menu_name_en = line

        # 원산지, 알러지 정보는 스킵
        elif line.startswith('*'):
            continue

        # 사이드 메뉴 (짧고 한글 위주)
        elif len(line) < 30 and not menu_name_en:
            # 메뉴명이 이미 설정된 후의 짧은 텍스트는 사이드 메뉴
            if menu_name and corner_name:
                side_items.append(line)

    if corner_name and menu_name:
        items = [{
            "name": menu_name,
            "name_en": menu_name_en,
            "rating": rating
        }]

        # 사이드 메뉴 추가
        for side in side_items:
            items.append({"name": side})

        return {
            "meal": current_meal,
            "corner": corner_name,
            "items": items
        }

    return None

def scrape_today():
    result = {
        "generated_at": _now_kr_iso(),
        "date": datetime.now(tz=tz.gettz("Asia/Seoul")).strftime("%Y-%m-%d"),
        "places": {}
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        try:
            print("페이지 접속 중...")
            page.goto(MOBILE_URL, wait_until="networkidle", timeout=30000)  # networkidle로 변경
            page.wait_for_timeout(10000)  # 초기 대기 시간 증가: 2000ms → 3000ms

            for t in TARGETS:
                place_data = {
                    "name": t["label"],
                    "building": t.get("building"),
                    "location_detail": t.get("location_detail"),
                    "menus": []
                }

                try:
                    print(f"\n{t['label']} 크롤링 중...")

                    # 식당 선택
                    page.select_option('select[name="rest"]', label=t["label"])

                    # 메뉴 로딩 대기 시간 대폭 증가: 1500ms → 3000ms
                    print(f"  메뉴 로딩 대기 중... (3초)")
                    page.wait_for_timeout(10000)

                    # 메뉴가 실제로 로드되었는지 확인 (최대 5초 대기)
                    try:
                        page.wait_for_selector("td.menu_list", state="visible", timeout=5000)
                    except:
                        print(f"  ⚠️  메뉴 로딩 타임아웃 - 추가 대기 중...")
                        page.wait_for_timeout(20000)  # 추가 2초 대기

                    # 모든 .menu_list 요소 가져오기 (각 코너마다 하나씩)
                    menu_cells = page.locator("td.menu_list").all()

                    if len(menu_cells) == 0:
                        print(f"  ⚠️  메뉴를 찾을 수 없습니다.")
                        result["places"][t["key"]] = place_data
                        continue

                    print(f"  발견된 메뉴 코너 수: {len(menu_cells)}")

                    # 각 코너별로 파싱
                    for idx, cell in enumerate(menu_cells):
                        try:
                            cell_text = cell.inner_text()
                            menu_info = parse_corner_text(cell_text)

                            if menu_info:
                                place_data["menus"].append(menu_info)
                                print(f"  ✓ [{idx+1}] {menu_info['corner']}: {menu_info['items'][0]['name']} (별점: {menu_info['items'][0].get('rating')})")
                            else:
                                print(f"  ⚠️  [{idx+1}] 파싱 실패")

                        except Exception as e:
                            print(f"  ✗ [{idx+1}] 에러: {e}")

                except Exception as e:
                    print(f"  ✗ 전체 에러: {e}")
                    import traceback
                    traceback.print_exc()

                result["places"][t["key"]] = place_data
                print(f"  ✅ 총 {len(place_data['menus'])}개 메뉴 수집 완료")

        except Exception as e:
            print(f"\n크롤링 전체 에러: {e}")
            import traceback
            traceback.print_exc()

        finally:
            browser.close()

    # JSON 저장
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 저장 완료: {OUT_PATH}")
    print(f"총 {sum(len(p['menus']) for p in result['places'].values())}개의 메뉴가 수집되었습니다.")

if __name__ == "__main__":
    scrape_today()
