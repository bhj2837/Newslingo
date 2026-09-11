"""
guardrails.py — 입력 가드레일 2단계 (설계서 3.3)

설계 원칙: 저비용 규칙 기반 필터를 먼저 적용하고, 통과분만 모델 기반 판별기로 넘긴다.

  1단계  입력 1차 필터  : 금칙어 정규식 매칭 → 모델 호출 없이 즉시 차단
  2단계  입력 2차 판별  : 모델2 + TopicGuardrailResult 구조화 출력으로 의미 판별

강의 [5] Advanced Agent "3. Guardrails" 의 before_agent / 규칙+모델 조합 패턴.
"""

from __future__ import annotations

import re

from langchain_core.prompts import ChatPromptTemplate

from .models import get_classifier_model
from .prompts import GUARDRAIL_SYSTEM_PROMPT
from .schemas import TopicGuardrailResult

# ──────────────────────────────────────────────────────────────
# 1단계 : 금칙어 사전 (설계서 3.3 입력 1차 필터, 심각도 High)
#   - 데모/수업용 최소 목록. 실제 서비스라면 외부 사전으로 분리 관리.
# ──────────────────────────────────────────────────────────────
_BANNED_PATTERNS: list[str] = [
    r"섹스|성인물|야동|야한|음란|포르노|19금",
    r"자살|폭탄\s*제조|테러",
    r"씨발|시발|병신|개새끼",
]
_BANNED_REGEX = re.compile("|".join(_BANNED_PATTERNS), re.IGNORECASE)


def rule_based_filter(user_text: str) -> TopicGuardrailResult | None:
    """1차 규칙 필터. 위반이면 차단 결과를, 통과면 None 을 반환한다."""
    if _BANNED_REGEX.search(user_text):
        return TopicGuardrailResult(
            allowed=False,
            block_reason="금칙어가 포함된 요청입니다. (1차 규칙 필터)",
        )
    return None


# ──────────────────────────────────────────────────────────────
# 2단계 : 모델2 기반 의미 판별 (설계서 3.3 입력 2차 판별)
#   강의 [3] "4. Structured Output" — with_structured_output(스키마)
# ──────────────────────────────────────────────────────────────
_classifier_chain = (
    ChatPromptTemplate.from_messages(
        [("system", GUARDRAIL_SYSTEM_PROMPT), ("human", "{user_text}")]
    )
    | get_classifier_model().with_structured_output(TopicGuardrailResult)
)


def model_based_filter(user_text: str) -> TopicGuardrailResult:
    """2차 분류 모델 판별. 항상 TopicGuardrailResult 를 반환한다."""
    return _classifier_chain.invoke({"user_text": user_text})


# ──────────────────────────────────────────────────────────────
# 통합 진입점
# ──────────────────────────────────────────────────────────────
def check_topic(user_text: str) -> TopicGuardrailResult:
    """학습 주제 요청을 2단계 가드레일에 통과시킨다 (설계서 2.2 1~2단계).

    1차에서 걸리면 모델을 호출하지 않고 즉시 차단 결과를 돌려준다.
    """
    blocked = rule_based_filter(user_text)
    if blocked is not None:
        return blocked
    return model_based_filter(user_text)
