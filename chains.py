"""
chains.py — LCEL 체인 (설계서 2.4 Structured Output 생성)

강의 [3] LangChain "5. LCEL" 의 `prompt | model | ...` 파이프라인 방식.
여기서는 파서 대신 `model.with_structured_output(스키마)` 를 붙여 Pydantic 객체를 바로 얻는다.

  - article_recommender_chain : news_search 원본 → ArticleCandidateList (5개)
  - study_material_chain       : 기사 본문 → ArticleStudyMaterial
  - quiz_chain                 : 기사 + 채팅 로그 → QuizSet (5문항)
"""

from __future__ import annotations

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable

from .models import get_main_model
from .prompts import (
    ARTICLE_RECOMMENDER_TEMPLATE,
    QUIZ_TEMPLATE,
    STUDY_MATERIAL_TEMPLATE,
)
from .schemas import ArticleCandidateList, ArticleStudyMaterial, QuizSet

# 메인 모델은 한 번만 만들어 세 체인이 공유한다.
_model = get_main_model()


def _build(template: str, schema: type) -> Runnable:
    """공통 조립기: PromptTemplate | model.with_structured_output(schema)."""
    return PromptTemplate.from_template(template) | _model.with_structured_output(schema)


# 설계서 2.2 4단계 — 기사 5개 추천
article_recommender_chain: Runnable = _build(
    ARTICLE_RECOMMENDER_TEMPLATE, ArticleCandidateList
)

# 설계서 2.2 6단계 — 학습자료 생성
study_material_chain: Runnable = _build(STUDY_MATERIAL_TEMPLATE, ArticleStudyMaterial)

# 설계서 2.2 9단계 — 퀴즈 5문항 생성 (테스트 TS-07)
quiz_chain: Runnable = _build(QUIZ_TEMPLATE, QuizSet)
