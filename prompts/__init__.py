"""
prompts 패키지 — 프롬프트 문자열을 담당자별 파일로 분리해서 관리한다.

  main.py        : 박서윤 (메인 모델1 System Prompt, 온보딩 문구)
  guardrail.py   : 박태식 (모델2 분류 프롬프트, 차단 안내 문구)
  generation.py  : 이지영 (기사추천/학습자료/퀴즈 생성 체인 템플릿)

다른 모듈은 예전처럼 `from .prompts import XXX` 로 그대로 쓰면 된다.
"""

from .generation import (
    ARTICLE_RECOMMENDER_TEMPLATE,
    QUIZ_TEMPLATE,
    STUDY_MATERIAL_TEMPLATE,
)
from .guardrail import GUARDRAIL_BLOCK_MESSAGE, GUARDRAIL_SYSTEM_PROMPT
from .main import MAIN_SYSTEM_PROMPT, ONBOARDING_MESSAGE

__all__ = [
    "MAIN_SYSTEM_PROMPT",
    "ONBOARDING_MESSAGE",
    "GUARDRAIL_SYSTEM_PROMPT",
    "GUARDRAIL_BLOCK_MESSAGE",
    "ARTICLE_RECOMMENDER_TEMPLATE",
    "STUDY_MATERIAL_TEMPLATE",
    "QUIZ_TEMPLATE",
]
