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
PRICE_PATTERN = re.compile(r"^(.*?)\s*(\d{1,3}(?:,\d{3})*원?|\d{4,}원?)$")

def _now_kr_iso():
    KST = tz.gettz("Asia/Seoul")
    return datetime.now(tz=KST).isoformat(timespec="seconds")

def parse_menu_item(text: str) -> dict:
    """메뉴 텍스트를 파싱하여 이름과 가격을 분리합니다."""
    text = text.replace("★", "").strip()
    match = PRICE_PATTERN.match(text)
    if match:
        name = match.group(1).strip()
        price = match.group(2).strip()
        if "원" not in price:
            price += "원"
        return {"name": name, "price": price}
    return {"name": text, "price": None}

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
            page.goto(MOBILE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

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
                    page.wait_for_timeout(1500)

                    # .menu_list 컨테이너에서 메뉴 추출
                    menu_container = page.locator(".menu_list")

                    if menu_container.count() == 0:
                        print(f"  ⚠️  메뉴 컨테이너를 찾을 수 없습니다.")
                        result["places"][t["key"]] = place_data
                        continue

                    # 전체 텍스트 추출
                    full_text = menu_container.inner_text()

                    # 코너별로 분리 (대괄호로 감싸진 부분)
                    corner_pattern = r'\[([^\]]+)\]'
                    corners = re.split(corner_pattern, full_text)

                    current_meal = "중식"  # 기본값

                    i = 1
                    while i < len(corners):
                        if i + 1 >= len(corners):
                            break

                        corner_name = corners[i].strip()
                        corner_content = corners[i + 1].strip()

                        # 코너 내용 파싱
                        lines = corner_content.split('\n')
                        items = []
                        menu_name = None
                        menu_name_en = None
                        rating = None

                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue

                            # 별점과 메뉴명 추출
                            if '★' in line and '-' in line:
                                parts = line.split('★')[1].strip().split('-')
                                if len(parts) == 2:
                                    menu_name = parts[0].strip()
                                    try:
                                        rating = float(parts[1].strip())
                                    except:
                                        rating = None
                            # 영문 메뉴명 (대문자로 시작하는 경우)
                            elif line and line[0].isupper() and ' ' in line and not line.startswith('*'):
                                menu_name_en = line
                            # 원산지, 알러지 정보는 스킵
                            elif line.startswith('*'):
                                continue
                            # 일반 메뉴 아이템
                            elif menu_name and not menu_name_en:
                                # 이미 메뉴명이 설정된 후의 줄들은 사이드 디시로 처리
                                if not line.startswith('*') and len(line) < 50:
                                    items.append({"name": line, "price": None})

                        # 메인 메뉴 정보 구성
                        if menu_name:
                            menu_info = {
                                "meal": current_meal,
                                "corner": corner_name,
                                "items": [{
                                    "name": menu_name,
                                    "name_en": menu_name_en,
                                    "price": None,
                                    "rating": rating
                                }]
                            }

                            # 사이드 메뉴 추가
                            if items:
                                menu_info["items"].extend(items)

                            place_data["menus"].append(menu_info)
                            print(f"  ✓ {corner_name}: {menu_name} (별점: {rating})")

                        i += 2

                except Exception as e:
                    print(f"  ✗ 에러 발생: {e}")
                    import traceback
                    traceback.print_exc()

                result["places"][t["key"]] = place_data
                print(f"  총 {len(place_data['menus'])}개 메뉴 수집 완료")

        except Exception as e:
            print(f"\n전체 에러: {e}")
            import traceback
            traceback.print_exc()

        finally:
            browser.close()

    # JSON 저장
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 저장 완료: {OUT_PATH}")

if __name__ == "__main__":
    scrape_today()
