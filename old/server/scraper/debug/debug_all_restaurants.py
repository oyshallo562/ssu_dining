# debug_all_restaurants.py

import json
from playwright.sync_api import sync_playwright
from pathlib import Path

TARGETS = [
    {"key": "students", "label": "학생식당"},
    {"key": "dodam", "label": "숭실도담식당"},
    {"key": "foodcourt", "label": "푸드코트"},
]

MOBILE_URL = "https://soongguri.com/m/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15"
    )
    page = context.new_page()

    page.goto(MOBILE_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)

    for t in TARGETS:
        print(f"\n{'='*60}")
        print(f"{t['label']} 분석 중...")
        print('='*60)

        page.select_option('select[name="rest"]', label=t["label"])
        page.wait_for_timeout(3000)

        # 모든 td.menu_list 가져오기
        menu_cells = page.locator("td.menu_list").all()
        print(f"\n발견된 td.menu_list 개수: {len(menu_cells)}")

        for idx, cell in enumerate(menu_cells):
            print(f"\n--- 셀 #{idx+1} ---")
            cell_text = cell.inner_text()
            print(cell_text)
            print(f"--- 셀 #{idx+1} 끝 ---")

        # 스크린샷 저장
        screenshot_path = Path(__file__).resolve().parent / f"debug_{t['key']}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\n스크린샷 저장: {screenshot_path}")

    input("\n엔터를 누르면 종료됩니다...")
    browser.close()
