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

    term: str = Field(
        description="기사 본문에 실제로 등장한 **영어** 단어 또는 표현. "
        "한국어로 쓰지 말 것. 예: 'threat intelligence', 'surveil'"
    )
    meaning: str = Field(description="그 영어 단어의 한국어 뜻풀이. 예: '위협 정보'")
    example: str = Field(
        description="기사 본문에서 그 단어가 쓰인 **영어 문장을 그대로 발췌**. "
        "새로 지어내지 말고 원문에 있는 문장을 사용할 것."
    )


class GrammarItem(BaseModel):
    """문법 포인트 항목."""

    pattern: str = Field(
        description="**영어** 문법 패턴을 영어 표기로. 한국어 문법(조사·어미)을 쓰지 말 것. "
        "예: 'have been + p.p. (현재완료 수동태)', 'according to + 명사'"
    )
    explanation: str = Field(description="그 영어 문법에 대한 한국어 설명")
    example: str = Field(
        description="기사 본문에서 그 문법이 실제로 쓰인 **영어 문장을 그대로 발췌**"
    )


class ArticleStudyMaterial(BaseModel):
    """선택한 기사에 대한 학습자료 묶음 (설계서 2.2 6단계)."""

    translated_text: str = Field(description="기사 전문의 자연스러운 한글 번역본")
    key_terms: list[TermItem] = Field(
        description="기사 주제 분야의 **전문 용어 영어 단어** 3~7개. "
        "그 분야를 모르면 사전을 찾아도 뜻이 잘 안 잡히는 단어를 고른다. "
        "기사가 길면 3개에서 멈추지 말고 5~7개를 채울 것.",
        min_length=3, max_length=7,
    )
    basic_vocab: list[TermItem] = Field(
        description="전문 용어가 아닌 **일반 영어 빈출 단어** 3~7개. "
        "학습자 난이도에 맞춰 고르고, key_terms 와 **겹치지 않게** 한다. "
        "기사가 길면 5~7개를 채울 것.",
        min_length=3, max_length=7,
    )
    grammar_points: list[GrammarItem] = Field(
        description="기사 문장에서 뽑은 **영어 문법** 포인트 1~3개", min_length=1, max_length=3
    )


# ──────────────────────────────────────────────────────────────
# 4. 퀴즈 (설계서 2.4 QuizSet / QuizQuestion)
# ──────────────────────────────────────────────────────────────
class QuizQuestion(BaseModel):
    """4지선다 퀴즈 1문항."""

    question: str = Field(
        description="Write the question in ENGLISH. Quote the article's original English "
        "wording when the question is about a word, phrase, or grammar point. "
        "Test ENGLISH ABILITY, not recall of the article's storyline."
    )
    choices: list[str] = Field(
        description="Exactly 4 options, all in ENGLISH. The 3 distractors must be the same "
        "part of speech, similar in length, and plausible, so the answer is not obvious at a "
        "glance. Never use escape options like 'none of the above'.",
        min_length=4, max_length=4,
    )
    answer: str = Field(
        description="The correct option — must match one of `choices` exactly, character for character"
    )
    explanation: str = Field(
        description="Explain in ENGLISH why the answer is correct AND why each distractor is wrong. "
        "Keep it short enough for a learner at the given level to follow."
    )


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
