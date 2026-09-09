"""구조화 집계만 사용하는 템플릿 및 선택적 Gemini 브리핑 adapter."""

import json
from collections.abc import Sequence
from typing import TypedDict

from src.reporting.monthly import MonthlySummary


class BriefingError(RuntimeError):
    """외부 브리핑 공급자 호출 실패."""


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


class ChatTurn(TypedDict):
    role: str
    content: str


class MonthlyReportChatbot:
    """월간 집계와 대화 이력을 사용하는 LangChain Gemini 챗봇."""

    def __init__(self, api_key: str, model: str, timeout_seconds: int = 20) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY가 필요합니다.")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _chat_model(self):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            timeout=self.timeout_seconds,
            temperature=0.4,
        )

    @staticmethod
    def _statistics(
        summary: MonthlySummary, previous: MonthlySummary
    ) -> dict[str, int | float | str]:
        return {
            "selected_month": summary.month,
            "trip_count": summary.trip_count,
            "walking_distance_km": round(summary.distance_m / 1_000, 3),
            "carbon_saved_kg_co2e": round(summary.carbon_saved_g / 1_000, 3),
            "taxi_saved_krw": summary.taxi_saved_krw,
            "previous_month": previous.month,
            "previous_trip_count": previous.trip_count,
            "previous_walking_distance_km": round(previous.distance_m / 1_000, 3),
            "previous_carbon_saved_kg_co2e": round(previous.carbon_saved_g / 1_000, 3),
            "previous_taxi_saved_krw": previous.taxi_saved_krw,
        }

    def reply(
        self,
        summary: MonthlySummary,
        previous: MonthlySummary,
        history: Sequence[ChatTurn],
        question: str,
    ) -> str:
        if not question.strip():
            raise ValueError("질문을 입력해 주세요.")
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

            statistics = json.dumps(self._statistics(summary, previous), ensure_ascii=False)
            system = SystemMessage(
                content=(
                    "당신은 서울 쾌적 경로 앱의 월간 이동 코치입니다. 제공된 구조화 통계와 "
                    "대화 내용에 근거해 사용자의 질문에 자연스러운 한국어로 답하세요. "
                    "리포트를 그대로 반복하지 말고 비교, 패턴, 다음 행동을 질문에 맞게 "
                    "설명하세요. 통계에 없는 이동 원인·건강 효과·안전성은 추측하지 마세요. "
                    "거리·비용·탄소를 새로 계산하거나 입력 통계를 수정하지 마세요. "
                    f"현재 통계: {statistics}"
                )
            )
            messages = [system]
            for turn in history[-8:]:
                message_type = HumanMessage if turn["role"] == "user" else AIMessage
                messages.append(message_type(content=turn["content"]))
            messages.append(HumanMessage(content=question.strip()))
            response = self._chat_model().invoke(messages)
            text = getattr(response, "text", None)
            if callable(text):
                text = text()
            if not text:
                content = response.content
                if isinstance(content, str):
                    text = content
                else:
                    text = "".join(
                        str(block.get("text", "")) for block in content if isinstance(block, dict)
                    )
            if not str(text).strip():
                raise BriefingError("Gemini가 빈 답변을 반환했습니다.")
            return str(text).strip()
        except BriefingError:
            raise
        except Exception as exc:
            raise BriefingError("Gemini 월간 챗봇 응답을 생성하지 못했습니다.") from exc
