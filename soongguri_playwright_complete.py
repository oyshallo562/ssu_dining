# soongguri_playwright_complete.py (수정된 전체 코드)

import json
import re
from datetime import datetime
from dateutil import tz
from playwright.sync_api import sync_playwright, Page
from pathlib import Path

# --- 상수 정의 ---

# 시간대 설정
KST = tz.gettz("Asia/Seoul")

# 식당 정보 (기숙사 식당 포함)
TARGETS = [
    {"key": "students", "label": "학생식당", "building": "학생회관", "location_detail": "2층"},
    {"key": "dodam", "label": "숭실도담식당", "building": "숭실도담", "location_detail": "생활관 1층"},
    {"key": "foodcourt", "label": "푸드코트", "building": "신양관", "location_detail": "1층"},
    {"key": "dorm", "label": "기숙사 식당", "building": "레지던스 홀", "location_detail": "B1층"},
]

SOONGGURI_URL = "https://soongguri.com/m/"
DORM_URL = "https://ssudorm.ssu.ac.kr:444/SShostel/mall_main.php?viewform=B0001_foodboard_list&board_no=1"
OUT_PATH = Path(__file__).resolve().parent / "menus.json"


# --- 유틸리티 함수 ---

def _now_kr_iso():
    """한국 시간 기준 ISO 형식의 현재 시간을 반환합니다."""
    return datetime.now(tz=KST).isoformat(timespec="seconds")


# --- soongguri.com 파싱 함수 (기존과 동일) ---

def parse_students_corner(text: str) -> dict:
    """학생식당 형식 파싱: [코너명] ★ 메뉴 - 별점"""
    lines = text.strip().split('\n')
    corner_name = None
    menu_name = None
    menu_name_en = None
    rating = None
    side_items = []
    current_meal = "중식"

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            corner_name = line[1:-1]
            if '천원의아침밥' in corner_name:
                current_meal = "조식"
        elif '★' in line and '-' in line:
            parts = line.split('★')[1].strip()
            if '-' in parts:
                name_part, rating_part = parts.rsplit('-', 1)
                menu_name = name_part.strip()
                try:
                    rating = float(rating_part.strip())
                except ValueError:
                    rating = None
        elif line and len(line) > 5 and line[0].isupper() and ' ' in line and not line.startswith('*'):
            alpha_count = sum(1 for c in line if c.isalpha())
            if alpha_count / len(line) > 0.5:
                menu_name_en = line
        elif line.startswith('*'):
            continue
        elif len(line) < 30 and not menu_name_en:
            if menu_name and corner_name:
                side_items.append(line)

    if corner_name and menu_name:
        items = [{"name": menu_name, "name_en": menu_name_en, "rating": rating}]
        for side in side_items:
            items.append({"name": side})
        return {"meal": current_meal, "corner": corner_name, "items": items}
    return None

def parse_dodam_corner(text: str) -> dict:
    """도담식당 형식 파싱: [코너명] ★ 메뉴1 ★ 메뉴2 ... 메뉴들- 별점"""
    lines = text.strip().split('\n')
    corner_name = None
    menu_names = []
    menu_name_en = None
    rating = None
    side_items = []
    current_meal = "중식"

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('[') and line.endswith(']'):
            corner_name = line[1:-1]
        elif line.startswith('★'):
            menu_name = line.replace('★', '').strip()
            if menu_name:
                menu_names.append(menu_name)
        elif '-' in line and any(char.isdigit() for char in line):
            if '-' in line:
                parts = line.rsplit('-', 1)
                if len(parts) == 2:
                    try:
                        rating = float(parts[1].strip())
                    except ValueError:
                        pass
        elif '(' in line and ')' in line and not line.startswith('*'):
            menu_name_en = line.strip('()')
        elif line.startswith('*'):
            continue
        elif len(line) < 30 and corner_name and menu_names:
            if not line.startswith('★') and not '-' in line:
                side_items.append(line)

    if corner_name and menu_names:
        main_menu_name = ' & '.join(menu_names)
        items = [{"name": main_menu_name, "name_en": menu_name_en, "rating": rating}]
        for side in side_items[:5]:
            if side and not any(word in side for word in ['알러지', '원산지']):
                items.append({"name": side})
        return {"meal": current_meal, "corner": corner_name, "items": items}
    return None


# --- 기숙사 식당 크롤링 함수 (수정됨) ---

def scrape_dorm_menu(page: Page) -> dict:
    """기숙사 식당 메뉴를 크롤링하고 파싱합니다."""
    dorm_target = next((t for t in TARGETS if t["key"] == "dorm"), None)
    if not dorm_target:
        return None

    place_data = {
        "name": dorm_target["label"],
        "building": dorm_target.get("building"),
        "location_detail": dorm_target.get("location_detail"),
        "menus": []
    }

    print(f"\n{dorm_target['label']} 크롤링 중...")
    try:
        page.goto(DORM_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # 오늘 요일 (월요일=0, ..., 일요일=6)
        today_weekday = datetime.now(tz=KST).weekday()
        # CSS nth-child는 1부터 시작. 첫 열이 '구분'이므로 +2
        # (월: 0+2=2, 화: 1+2=3, ..., 일: 6+2=8)
        today_col_index = today_weekday + 2

        meal_types = {"조식": "조식", "중식": "중식", "석식": "석식"}
        rows = page.locator(".ht_area tbody tr").all()

        for row in rows:
            meal_name = row.locator("td").first.inner_text().strip()
            if meal_name in meal_types:
                menu_cell = row.locator(f"td:nth-child({today_col_index})")

                # inner_html을 사용하여 <br> 태그로 분리
                cell_html = menu_cell.inner_html()

                # HTML 태그 제거 및 공백 정리
                menu_items_raw = re.split(r'\s*<br\s*/?>\s*', cell_html.strip())

                # 비어있거나 특정 단어가 포함된 항목 제외
                items = [
                    {"name": item.strip()}
                    for item in menu_items_raw
                    if item.strip() and "운영없음" not in item and "휴무" not in item
                ]

                if items:
                    place_data["menus"].append({
                        "meal": meal_types[meal_name],
                        "corner": "오늘의 메뉴",  # 기숙사는 코너가 없음
                        "items": items
                    })
                    print(f"  ✓ [{meal_types[meal_name]}] {items[0]['name']} 등 {len(items)}개 메뉴 발견")

        print(f"  ✅ 총 {len(place_data['menus'])}개 식사 수집 완료")
        return place_data

    except Exception as e:
        print(f"  ✗ 기숙사 식당 크롤링 에러: {e}")
        import traceback
        traceback.print_exc()
        return place_data


# --- 메인 크롤링 함수 (기존과 동일) ---

def scrape_today():
    """soongguri.com과 기숙사 식당 메뉴를 모두 스크랩하여 JSON으로 저장합니다."""
    result = {
        "generated_at": _now_kr_iso(),
        "date": datetime.now(tz=KST).strftime("%Y-%m-%d"),
        "places": {}
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        try:
            # 1. soongguri.com 크롤링
            soongguri_targets = [t for t in TARGETS if t["key"] != "dorm"]
            print("soongguri.com 페이지 접속 중...")
            page.goto(SOONGGURI_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            for t in soongguri_targets:
                place_data = {
                    "name": t["label"], "building": t.get("building"),
                    "location_detail": t.get("location_detail"), "menus": []
                }
                print(f"\n{t['label']} 크롤링 중...")
                page.select_option('select[name="rest"]', label=t["label"])
                page.wait_for_timeout(2000)

                body_text = page.locator("body").inner_text()
                if t["key"] == "foodcourt" and ("오늘은 쉽니다" in body_text or "휴무" in body_text):
                    print("  ⚠️  오늘은 휴무입니다.")
                else:
                    try:
                        page.wait_for_selector("td.menu_list", state="visible", timeout=5000)
                        menu_cells = page.locator("td.menu_list").all()
                        print(f"  발견된 메뉴 코너 수: {len(menu_cells)}")
                        for idx, cell in enumerate(menu_cells):
                            parser = parse_students_corner if t["key"] == "students" else parse_dodam_corner
                            menu_info = parser(cell.inner_text())
                            if menu_info:
                                place_data["menus"].append(menu_info)
                                print(f"  ✓ [{idx+1}] {menu_info['corner']}: {menu_info['items'][0]['name']}")
                            else:
                                print(f"  ⚠️  [{idx+1}] 파싱 실패")
                    except Exception:
                        print("  ⚠️  메뉴를 찾을 수 없습니다.")

                result["places"][t["key"]] = place_data
                print(f"  ✅ 총 {len(place_data['menus'])}개 메뉴 수집 완료")

            # 2. 기숙사 식당 크롤링
            dorm_data = scrape_dorm_menu(page)
            if dorm_data:
                result["places"]["dorm"] = dorm_data

        except Exception as e:
            print(f"\n크롤링 전체 에러: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

    # 최종 JSON 저장
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total_menus = sum(len(p.get('menus', [])) for p in result['places'].values())
    print(f"\n✅ 저장 완료: {OUT_PATH}")
    print(f"총 {total_menus}개의 메뉴가 수집되었습니다.")

if __name__ == "__main__":
    scrape_today()