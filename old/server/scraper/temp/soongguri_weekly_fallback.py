# soongguri_weekly_fallback.py

import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import tz
from pathlib import Path

URL = "https://soongguri.com/main.php?l=2&mkey=2&w=3"  # 주간 식단
OUT_PATH = Path(__file__).resolve().parent / "data" / "menus.json"

# 메인 스크래퍼와 정보 통일
PLACES = [
    {"key": "students", "label": "학생식당", "building": "학생회관", "location_detail": "2층"},
    {"key": "dodam", "label": "숭실도담식당", "building": "숭실도담", "location_detail": "생활관 1층"},
    {"key": "foodcourt", "label": "푸드코트", "building": "신양관", "location_detail": "1층"},
]

STAR = re.compile(r"^★\s*(.+)$")


def _now_kr_iso():
    return datetime.now(tz=tz.gettz("Asia/Seoul")).isoformat(timespec="seconds")


def scrape_weekly_pick_today():
    try:
        html = requests.get(URL, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
    except requests.RequestException as e:
        print(f"Failed to fetch weekly menu: {e}")
        return

    # pre 태그 안의 텍스트를 가져와서 파싱
    content = soup.find("pre")
    if not content:
        print("Weekly menu content not found in <pre> tag.")
        return

    text = content.get_text("\n")

    result = {
        "generated_at": _now_kr_iso(),
        "date": datetime.now(tz=tz.gettz("Asia/Seoul")).strftime("%Y-%m-%d"),
        "places": {}
    }

    for place_info in PLACES:
        key = place_info["key"]
        label = place_info["label"]

        place_data = {
            "name": label,
            "building": place_info.get("building"),
            "location_detail": place_info.get("location_detail"),
            "menus": []
        }

        # 텍스트에서 해당 식당 영역을 찾음
        if label in text:
            after = text.split(label, 1)[1]

            # 다른 식당 이름이 나오기 전까지의 텍스트 블록을 자름
            next_labels = [p["label"] for p in PLACES if p["label"] != label]
            cut_idx = len(after)
            for nl in next_labels:
                if nl in after:
                    cut_idx = min(cut_idx, after.find(nl))
            block = after[:cut_idx]

            items = []
            for line in block.split("\n"):
                m = STAR.match(line)
                if m:
                    # 주간 메뉴는 가격 정보가 없으므로 메뉴 이름만 추가
                    item_name = m.group(1).strip()
                    items.append({"name": item_name, "price": None})

            # 주간 메뉴는 식사/코너 구분이 어려우므로 '중식'으로 통일
            if items:
                place_data["menus"].append({
                    "meal": "중식",
                    "corner": "대표메뉴",
                    "items": items
                })

        result["places"][key] = place_data

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"saved -> {OUT_PATH}")


if __name__ == "__main__":
    scrape_weekly_pick_today()