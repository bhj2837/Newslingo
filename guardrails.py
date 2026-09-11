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
#
#   우회 방지(글자 사이 공백/특수문자 삽입 허용)는 3글자 이상 단어에만 적용한다.
#   2글자 단어(씨발/야동 등)에 적용하면 "무씨 발아율"처럼 무관한 단어가 스페이스
#   하나만으로 오탐될 위험이 실제로 있어(검증함), 2글자 이하는 정확 일치만 쓴다.
# ──────────────────────────────────────────────────────────────
_BANNED_WORDS: list[str] = [
    # 성적 콘텐츠
    "성인물", "야한", "음란", "포르노", "19금",
    # 폭력/자해/테러
    "자살", "폭탄제조", "테러",
    # 욕설
    "씨발", "시발", "병신", "개새끼",
]

_EVASION_FILLER = r"[\s.,\-_*~]{0,2}"


def _to_pattern(word: str) -> str:
    """단어를 매칭용 정규식 조각으로 변환.

    3글자 이상: 글자 사이에 공백/구두점/특수문자가 최대 2개까지 끼어도 잡아낸다
    (예: "폭 탄 제조", "포.르.노").
    2글자 이하: 오탐 위험이 커서 우회 방지 없이 정확 일치만 사용한다.
    """
    escaped_chars = [re.escape(ch) for ch in word]
    if len(word) >= 3:
        return _EVASION_FILLER.join(escaped_chars)
    return "".join(escaped_chars)


_BANNED_REGEX = re.compile(
    "|".join(_to_pattern(w) for w in _BANNED_WORDS), re.IGNORECASE
)


def rule_based_filter(user_text: str) -> TopicGuardrailResult | None:
    """1차 규칙 필터. 위반이면 차단 결과를, 통과면 None 을 반환한다."""
    if not user_text or not user_text.strip():
        # 빈 입력은 모델까지 보낼 필요가 없음 (설계서 1.5: 불필요한 모델 호출 최소화)
        return TopicGuardrailResult(
            allowed=False,
            block_reason="빈 입력입니다. 학습하고 싶은 주제를 입력해주세요.",
        )
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


# 2차 판별 모델에 넘기기 전 입력 길이 상한 (설계서 1.5 성능: 비용/속도 방어).
# 학습 주제 요청은 보통 한두 문장이면 충분하므로 넉넉하게 잡음.
_MAX_INPUT_CHARS = 500


def model_based_filter(user_text: str) -> TopicGuardrailResult:
    """2차 분류 모델 판별. 항상 TopicGuardrailResult 를 반환한다."""
    return _classifier_chain.invoke({"user_text": user_text[:_MAX_INPUT_CHARS]})


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
