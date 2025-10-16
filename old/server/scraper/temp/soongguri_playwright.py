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
        page.goto(MOBILE_URL, wait_until="domcontentloaded")  # 페이지 로딩 전략 변경
        page.wait_for_timeout(1000)  # 데이터 로딩 대기

        for t in TARGETS:
            place_data = {
                "name": t["label"],
                "building": t.get("building"),
                "location_detail": t.get("location_detail"),
                "menus": []
            }

            try:
                # --- START: 핵심 수정 부분 ---
                # 기존의 탭 클릭 방식 대신, 드롭다운 메뉴에서 식당을 선택합니다.
                # select_option은 <select> 태그를 찾아 내부 <option>을 선택하는 Playwright 기능입니다.
                page.select_option('select[name="rest"]', label=t["label"])
                page.wait_for_timeout(500)  # 메뉴가 바뀔 때까지 잠시 대기
                # --- END: 핵심 수정 부분 ---

                # 식당별 메뉴 컨테이너를 더 안정적인 ID 선택자로 변경
                container = page.locator("#menu_list")

                meal_sections = container.locator(".menu_title")

                current_meal = "중식"

                for i in range(meal_sections.count()):
                    meal_title_element = meal_sections.nth(i)
                    meal_title = meal_title_element.inner_text().strip()

                    if "아침" in meal_title:
                        current_meal = "아침"
                    elif "점심" in meal_title:
                        current_meal = "중식"
                    elif "저녁" in meal_title:
                        current_meal = "석식"

                    menu_block = meal_title_element.locator("xpath=following-sibling::div[1]")

                    corners = menu_block.locator("strong")
                    for j in range(corners.count()):
                        corner_element = corners.nth(j)
                        corner_name = corner_element.inner_text().strip()

                        menu_list_element = corner_element.locator("xpath=following-sibling::ul[1]")

                        items = []
                        if menu_list_element.count() > 0:
                            menu_items_text = menu_list_element.all_text_contents()
                            raw_text = "\n".join(menu_items_text)
                            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

                            for line in lines:
                                items.append(parse_menu_item(line))

                        if items:
                            place_data["menus"].append({
                                "meal": current_meal,
                                "corner": corner_name,
                                "items": items
                            })
            except Exception as e:
                print(f"Error scraping {t['label']}: {e}")
                place_data["menus"] = []

            result["places"][t["key"]] = place_data

        browser.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"saved -> {OUT_PATH}")


if __name__ == "__main__":
    scrape_today()