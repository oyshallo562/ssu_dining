# soongguri_playwright.py

import json
import re
from datetime import datetime
from dateutil import tz
from playwright.sync_api import sync_playwright
from pathlib import Path

# 식당 정보는 변경 없음
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
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        # 페이지 로딩 개선
        page.goto(MOBILE_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)  # 충분한 대기 시간

        for t in TARGETS:
            place_data = {
                "name": t["label"],
                "building": t.get("building"),
                "location_detail": t.get("location_detail"),
                "menus": []
            }

            try:
                # 드롭다운에서 식당 선택
                page.select_option('select[name="rest"]', label=t["label"])
                page.wait_for_timeout(1500)  # 메뉴 로딩 대기 시간 증가

                # 메뉴 데이터가 로드될 때까지 대기
                page.wait_for_selector("#menu_list", state="visible", timeout=5000)

                # 식당별 메뉴 컨테이너
                container = page.locator("#menu_list")

                # 메뉴가 있는지 확인
                if container.count() == 0:
                    print(f"{t['label']}: #menu_list를 찾을 수 없습니다.")
                    result["places"][t["key"]] = place_data
                    continue

                # 식사 시간대별 섹션 찾기 (개선된 선택자)
                meal_sections = container.locator("div.menu_section, div[class*='menu']")

                if meal_sections.count() == 0:
                    # 대체 방법: 모든 div 검사
                    all_divs = container.locator("div")
                    print(f"{t['label']}: {all_divs.count()}개의 div 발견")

                    # HTML 구조 출력 (디버깅용)
                    html_content = container.inner_html()
                    print(f"{t['label']} HTML 일부:\n{html_content[:500]}")

                current_meal = "중식"

                # 전체 텍스트 추출 방식으로 변경
                full_text = container.inner_text()
                print(f"\n{t['label']} 전체 텍스트:\n{full_text[:300]}...")

                # 텍스트 기반 파싱
                lines = full_text.split("\n")
                current_corner = None
                items = []

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # 식사 시간대 감지
                    if "아침" in line or "조식" in line:
                        if current_corner and items:
                            place_data["menus"].append({
                                "meal": current_meal,
                                "corner": current_corner,
                                "items": items
                            })
                            items = []
                        current_meal = "아침"
                        current_corner = None
                    elif "점심" in line or "중식" in line or "중" == line:
                        if current_corner and items:
                            place_data["menus"].append({
                                "meal": current_meal,
                                "corner": current_corner,
                                "items": items
                            })
                            items = []
                        current_meal = "중식"
                        current_corner = None
                    elif "저녁" in line or "석식" in line:
                        if current_corner and items:
                            place_data["menus"].append({
                                "meal": current_meal,
                                "corner": current_corner,
                                "items": items
                            })
                            items = []
                        current_meal = "석식"
                        current_corner = None
                    # 코너명 감지 (숫자나 가격이 없는 짧은 텍스트)
                    elif not re.search(r"\d{3,}", line) and len(line) < 20 and current_corner is None:
                        if items and current_corner:
                            place_data["menus"].append({
                                "meal": current_meal,
                                "corner": current_corner,
                                "items": items
                            })
                        current_corner = line
                        items = []
                    # 메뉴 아이템 (가격 포함 가능성 높음)
                    elif current_corner:
                        parsed = parse_menu_item(line)
                        if parsed["name"]:
                            items.append(parsed)

                # 마지막 항목 저장
                if current_corner and items:
                    place_data["menus"].append({
                        "meal": current_meal,
                        "corner": current_corner,
                        "items": items
                    })

            except Exception as e:
                print(f"Error scraping {t['label']}: {e}")
                import traceback
                traceback.print_exc()
                place_data["menus"] = []

            result["places"][t["key"]] = place_data
            print(f"{t['label']}: {len(place_data['menus'])}개 메뉴 수집 완료")

        browser.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {OUT_PATH}")

if __name__ == "__main__":
    scrape_today()
