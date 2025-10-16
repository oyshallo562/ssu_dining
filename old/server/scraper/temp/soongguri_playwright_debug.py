# soongguri_playwright_fixed_v2.py

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
        browser = p.chromium.launch(headless=False)  # 디버깅을 위해 headless=False
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        try:
            # 페이지 접속
            print("페이지 접속 중...")
            page.goto(MOBILE_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # 페이지 내용 확인
            print("\n=== 페이지 타이틀 ===")
            print(page.title())

            # 전체 HTML 구조 출력
            print("\n=== 페이지 HTML 구조 (처음 2000자) ===")
            html_content = page.content()
            print(html_content[:2000])

            # select 태그가 있는지 확인
            print("\n=== Select 태그 확인 ===")
            selects = page.locator("select").all()
            print(f"발견된 select 태그 개수: {len(selects)}")

            for idx, select in enumerate(selects):
                try:
                    name = select.get_attribute("name")
                    options = select.locator("option").all()
                    print(f"\nSelect #{idx} - name: {name}")
                    print(f"  옵션 개수: {len(options)}")
                    for opt in options[:5]:  # 처음 5개만 출력
                        print(f"    - {opt.inner_text()}")
                except Exception as e:
                    print(f"  에러: {e}")

            # 주요 div 구조 확인
            print("\n=== 메인 컨테이너 확인 ===")
            main_containers = ["#menu_list", ".menu_list", "#content", ".content", "main", ".container"]
            for selector in main_containers:
                try:
                    elem = page.locator(selector).first
                    if elem.count() > 0:
                        print(f"✓ 발견: {selector}")
                        print(f"  내용 미리보기: {elem.inner_text()[:200]}")
                except:
                    print(f"✗ 없음: {selector}")

            # 스크린샷 저장
            screenshot_path = Path(__file__).resolve().parent / "debug_screenshot.png"
            page.screenshot(path=str(screenshot_path))
            print(f"\n스크린샷 저장됨: {screenshot_path}")

        except Exception as e:
            print(f"\n에러 발생: {e}")
            import traceback
            traceback.print_exc()

        finally:
            input("\n엔터를 누르면 브라우저가 종료됩니다...")
            browser.close()

    # 빈 결과 저장
    for t in TARGETS:
        result["places"][t["key"]] = {
            "name": t["label"],
            "building": t.get("building"),
            "location_detail": t.get("location_detail"),
            "menus": []
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {OUT_PATH}")

if __name__ == "__main__":
    scrape_today()
