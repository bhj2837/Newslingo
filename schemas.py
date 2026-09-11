"""
schemas.py — Structured Output 정의 (설계서 2.4)

강의 [3] LangChain "4. Structured Output" 에서 배운 Pydantic 방식.
model.with_structured_output(스키마) 또는 ToolStrategy(스키마) 로 사용한다.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .config import LEVELS


# ──────────────────────────────────────────────────────────────
# 1. 입력 가드레일 결과 (설계서 3.3 입력 2차 판별 / 모델2)
# ──────────────────────────────────────────────────────────────
class TopicGuardrailResult(BaseModel):
    """1차 규칙 필터를 통과한 학습 주제 요청이 의미상 적절한지 판별한 결과."""

    allowed: bool = Field(description="요청 허용 여부")
    block_reason: Optional[str] = Field(
        default=None, description="차단 사유. allowed=False 일 때만 값이 존재"
    )
    extracted_topic: Optional[str] = Field(
        default=None,
        description="입력에서 추출한 학습 주제(영문 뉴스 검색어로 쓰기 좋은 형태). "
        "allowed=True 일 때만 값이 존재",
    )


# ──────────────────────────────────────────────────────────────
# 2. 기사 추천 (설계서 2.4 ArticleCandidate / ArticleCandidateList)
# ──────────────────────────────────────────────────────────────
class ArticleCandidate(BaseModel):
    """추천 기사 1건."""

    title: str = Field(description="기사 제목")
    url: str = Field(description="기사 원문 링크")
    summary: str = Field(description="한 줄 요약", max_length=100)
    source: str = Field(description="출처 매체명")
    published_date: str = Field(description="기사 발행일 (YYYY-MM-DD)")
    keywords: list[str] = Field(description="핵심 키워드 2~5개", min_length=2, max_length=5)


class ArticleCandidateList(BaseModel):
    """추천 기사 후보 목록 — 정확히 5개."""

    articles: list[ArticleCandidate] = Field(
        description="현재 난이도와 주제를 반영한 추천 기사 5개",
        min_length=5,
        max_length=5,
    )


# ──────────────────────────────────────────────────────────────
# 3. 학습자료 (설계서 2.4 ArticleStudyMaterial / TermItem / GrammarItem)
# ──────────────────────────────────────────────────────────────
class TermItem(BaseModel):
    """단어 항목 (전문 용어 / 기본 핵심 단어 공용)."""

    term: str = Field(description="단어 또는 표현")
    meaning: str = Field(description="한글 뜻")
    example: str = Field(description="해당 단어가 쓰인 예문")


class GrammarItem(BaseModel):
    """문법 포인트 항목."""

    pattern: str = Field(description="문법 패턴 (예: 'have been + p.p.')")
    explanation: str = Field(description="문법 설명")
    example: str = Field(description="기사에서 발췌하거나 만든 예문")


class ArticleStudyMaterial(BaseModel):
    """선택한 기사에 대한 학습자료 묶음 (설계서 2.2 6단계)."""

    translated_text: str = Field(description="기사 전문의 자연스러운 한글 번역본")
    key_terms: list[TermItem] = Field(
        description="기사에 등장하는 전문 용어 3~7개", min_length=3, max_length=7
    )
    basic_vocab: list[TermItem] = Field(
        description="학습자 눈높이의 기본 핵심 단어 3~7개", min_length=3, max_length=7
    )
    grammar_points: list[GrammarItem] = Field(
        description="주요 문법 포인트 1~3개", min_length=1, max_length=3
    )


# ──────────────────────────────────────────────────────────────
# 4. 퀴즈 (설계서 2.4 QuizSet / QuizQuestion)
# ──────────────────────────────────────────────────────────────
class QuizQuestion(BaseModel):
    """4지선다 퀴즈 1문항."""

    question: str = Field(description="문제 (한글로 출제, 필요 시 영어 지문 인용)")
    choices: list[str] = Field(description="선택지 4개", min_length=4, max_length=4)
    answer: str = Field(description="정답 — choices 중 하나와 정확히 일치해야 함")
    explanation: str = Field(description="정답 해설")


class QuizSet(BaseModel):
    """기사 + 채팅 로그에 근거한 퀴즈 5문항 (설계서 2.2 9단계)."""

    questions: list[QuizQuestion] = Field(
        description="정확히 5문항", min_length=5, max_length=5
    )


# ──────────────────────────────────────────────────────────────
# 5. 채점 & 난이도 추천 (설계서 2.2 10~11단계) — 로직 계산 결과용 내부 스키마
# ──────────────────────────────────────────────────────────────
class GradedAnswer(BaseModel):
    """문항별 채점 결과."""

    question: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str


class QuizResult(BaseModel):
    """퀴즈 전체 채점 결과."""

    total: int
    correct: int
    accuracy: float = Field(description="정답률 0.0 ~ 1.0")
    details: list[GradedAnswer]


class LevelRecommendation(BaseModel):
    """정답률에 따른 난이도 조정 추천 (실제 반영은 HITL 승인 후)."""

    direction: Literal["up", "down", "keep"] = Field(description="상향 / 하향 / 유지")
    current_level: str
    suggested_level: str
    message: str = Field(description="사용자에게 보여줄 추천 문구")

    def is_change(self) -> bool:
        return self.direction != "keep" and self.suggested_level in LEVELS
