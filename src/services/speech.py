"""Gemini TTS를 이용한 선택적 보행 안내 음성 adapter."""

from __future__ import annotations

import io
import wave


class SpeechError(RuntimeError):
    pass


class GeminiSpeechProvider:
    def __init__(self, api_key: str, model: str = "gemini-3.1-flash-tts-preview") -> None:
        self.api_key = api_key
        self.model = model

    def synthesize(self, instruction: str) -> bytes:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=(
                    "차분하고 명확한 한국어 보행 안내 음성으로 그대로 읽으세요: "
                    f"{instruction}"
                ),
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                        )
                    ),
                ),
            )
            pcm = response.candidates[0].content.parts[0].inline_data.data
            output = io.BytesIO()
            with wave.open(output, "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(24_000)
                stream.writeframes(pcm)
            return output.getvalue()
        except Exception as exc:
            raise SpeechError("Gemini 음성 안내를 생성하지 못했습니다.") from exc
