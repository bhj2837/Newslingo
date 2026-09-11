"""
models.py — LLM 인스턴스 생성 (설계서 2.3)

강의 [3] LangChain "1. Chat Model" 의 init_chat_model 방식 그대로 사용.
  - 모델1(메인)  : 대화·생성 전반
  - 모델2(분류)  : 입력 가드레일 전용, Temperature 0
"""

from __future__ import annotations

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from . import config


def get_main_model() -> BaseChatModel:
    """모델1 — 메인 대화/생성 모델 (설계서 2.3 모델1)."""
    return init_chat_model(
        config.MAIN_MODEL,
        temperature=config.MAIN_TEMPERATURE,
        timeout=30,  # 강의 [3]: 장애 방지용 timeout
    )


def get_classifier_model() -> BaseChatModel:
    """모델2 — 입력 가드레일 분류 모델 (설계서 2.3 모델2).

    판별 일관성이 중요하므로 Temperature 0 으로 별도 호출한다.
    """
    return init_chat_model(
        config.CLASSIFIER_MODEL,
        temperature=config.CLASSIFIER_TEMPERATURE,
        timeout=15,
    )
