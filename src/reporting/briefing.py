"""구조화 집계만 사용하는 템플릿 및 선택적 Gemini 브리핑 adapter."""

import json
from typing import Protocol

import requests

from src.reporting.monthly import MonthlySummary


class BriefingError(RuntimeError):
    """외부 브리핑 공급자 호출 실패."""


class BriefingProvider(Protocol):
    def generate(self, summary: MonthlySummary) -> str:
        """이미 계산된 월간 집계를 설명한다."""


class TemplateBriefingProvider:
    def generate(self, summary: MonthlySummary) -> str:
        if summary.trip_count == 0:
            return f"{summary.month}에는 아직 완료한 도보 이동이 없습니다."
        return (
            f"{summary.month}에는 {summary.trip_count}번 이동해 총 "
            f"{summary.distance_m / 1_000:.2f}km를 걸었습니다. 승용차 이동을 대체했다고 "
            f"가정한 탄소 절감량은 {summary.carbon_saved_g / 1_000:.2f}kgCO₂e이며, "
            f"택시 대신 걸었다고 확인한 이동의 추정 절감액은 "
            f"{summary.taxi_saved_krw:,}원입니다."
        )


class GeminiBriefingProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: int = 20) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY가 필요합니다.")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, summary: MonthlySummary) -> str:
        statistics = {
            "month": summary.month,
            "trip_count": summary.trip_count,
            "walking_distance_km": round(summary.distance_m / 1_000, 3),
            "carbon_saved_kg_co2e": round(summary.carbon_saved_g / 1_000, 3),
            "taxi_saved_krw": summary.taxi_saved_krw,
        }
        prompt = (
            "다음은 코드가 이미 계산한 월간 도보 통계입니다. 수치를 다시 계산하거나 "
            "새 수치를 만들지 말고, 과장 없이 한국어 두 문장으로 설명하세요.\n"
            + json.dumps(statistics, ensure_ascii=False)
        )
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        try:
            response = requests.post(
                url,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            return str(payload["candidates"][0]["content"]["parts"][0]["text"]).strip()
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise BriefingError("Gemini 브리핑을 생성하지 못했습니다.") from exc
