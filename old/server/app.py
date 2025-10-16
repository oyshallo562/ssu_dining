# app.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
from datetime import datetime
import uvicorn  # uvicorn 실행을 위해 추가

# Pydantic 모델을 사용하면 API의 입출력을 더 명확하게 정의할 수 있습니다.
# from pydantic import BaseModel, Field
# from typing import List, Optional

DATA_PATH = Path(__file__).parent / "data" / "menus.json"

app = FastAPI(
    title="SSU Dining API",
    version="1.0.0",  # 버전 업데이트
    description="숭실대학교 학생식당 메뉴 정보 제공 API (개선 버전)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 프로덕션에서는 특정 도메인만 허용하는 것이 안전합니다.
    allow_credentials=True,
    allow_methods=["GET"],  # POST는 reload 용도이므로 GET만 허용해도 무방
)

# 데이터 캐싱을 위한 간단한 전역 변수
# API 호출 시마다 파일을 읽는 부담을 줄여줍니다.
_cache = {}


def load_data(force_reload: bool = False):
    """
    menus.json 파일을 읽어와 캐시에 저장하고 반환합니다.
    force_reload가 True이면 캐시를 무시하고 다시 파일을 읽습니다.
    """
    now = datetime.now()
    if not force_reload and "data" in _cache and (now - _cache.get("loaded_at", now)).total_seconds() < 60:
        return _cache["data"]

    if not DATA_PATH.exists():
        raise HTTPException(status_code=503, detail="menus.json 파일을 찾을 수 없습니다. 스크래퍼를 먼저 실행해주세요.")

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        _cache["data"] = data
        _cache["loaded_at"] = now
        return data


@app.get("/")
async def read_root():
    return {"message": "SSU Dining API에 오신 것을 환영합니다. /docs 로 API 문서를 확인하세요."}


@app.get("/api/places")
async def get_places():
    """등록된 모든 식당의 기본 정보를 반환합니다."""
    data = load_data()
    # places의 value 전체를 반환하도록 변경하여 더 많은 정보 제공
    return list(data.get("places", {}).values())


@app.get("/api/today")
async def get_today(places: str | None = None):
    """
    오늘의 전체 식단 정보를 반환합니다. places 파라미터로 특정 식당만 필터링할 수 있습니다.
    (예: /api/today?places=students,foodcourt)
    """
    data = load_data()
    if places:
        # 쉼표로 구분된 문자열을 set으로 만들어 필터링
        keys_to_filter = {p.strip() for p in places.split(",") if p.strip()}
        # data["places"]의 복사본을 만들어 필터링
        filtered_places = {k: v for k, v in data.get("places", {}).items() if k in keys_to_filter}
        # 원본 데이터 구조를 유지하며 places만 교체
        return {**data, "places": filtered_places}
    return data


@app.post("/api/reload")
async def reload_from_disk():
    """
    디스크에서 menus.json 파일을 강제로 다시 읽어 캐시를 갱신합니다.
    스크래퍼 실행 직후 호출하면 좋습니다.
    """
    load_data(force_reload=True)
    return {
        "ok": True,
        "message": "데이터를 새로고침했습니다.",
        "reloaded_at": datetime.now().isoformat(timespec="seconds")
    }


# 이 파일이 직접 실행될 때 uvicorn 서버를 구동
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)