"""
grading.py — 퀴즈 채점 & 난이도 추천 로직 (설계서 2.2 10~11단계)

LLM 없이 순수 파이썬으로 계산한다. (일관성·재현성 확보, 테스트 TS-08)
실제 난이도 변경은 여기서 하지 않는다 → update_preference Tool + HITL 승인 후에만 반영.
"""

from __future__ import annotations

from . import config
from .schemas import (
    GradedAnswer,
    LevelRecommendation,
    QuizResult,
    QuizSet,
)


def _norm(text: str) -> str:
    return text.strip().lower()


def grade_quiz(quiz: QuizSet, user_answers: list[str]) -> QuizResult:
    """사용자 답안을 채점한다.

    Args:
        quiz: 출제된 QuizSet (5문항)
        user_answers: 문항 순서대로의 사용자 선택지 문자열 (choices 중 하나)
    """
    if len(user_answers) != len(quiz.questions):
        raise ValueError(
            f"답안 개수({len(user_answers)})가 문항 수({len(quiz.questions)})와 다릅니다."
        )

    details: list[GradedAnswer] = []
    for question, user_answer in zip(quiz.questions, user_answers):
        is_correct = _norm(user_answer) == _norm(question.answer)
        details.append(
            GradedAnswer(
                question=question.question,
                user_answer=user_answer,
                correct_answer=question.answer,
                is_correct=is_correct,
                explanation=question.explanation,
            )
        )

    correct = sum(1 for d in details if d.is_correct)
    total = len(details)
    return QuizResult(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        details=details,
    )


def recommend_level(accuracy: float, current_level: str) -> LevelRecommendation:
    """정답률에 따라 난이도 상향/하향/유지를 추천한다 (설계서 2.2 11단계).

    - 정답률 >= 80% : 상향 추천
    - 정답률 <= 40% : 하향 추천
    - 그 외          : 유지
    경계에서 더 올릴/내릴 난이도가 없으면 유지로 처리한다.
    """
    levels = config.LEVELS
    idx = levels.index(current_level) if current_level in levels else 1

    if accuracy >= config.LEVEL_UP_THRESHOLD and idx < len(levels) - 1:
        target = levels[idx + 1]
        return LevelRecommendation(
            direction="up",
            current_level=current_level,
            suggested_level=target,
            message=f"정답률이 {accuracy:.0%}로 높아요. 다음부터 '{target}' 난이도로 올려드릴까요?",
        )

    if accuracy <= config.LEVEL_DOWN_THRESHOLD and idx > 0:
        target = levels[idx - 1]
        return LevelRecommendation(
            direction="down",
            current_level=current_level,
            suggested_level=target,
            message=f"정답률이 {accuracy:.0%}예요. '{target}' 난이도로 낮춰서 천천히 가볼까요?",
        )

    return LevelRecommendation(
        direction="keep",
        current_level=current_level,
        suggested_level=current_level,
        message=f"정답률 {accuracy:.0%}. 지금 '{current_level}' 난이도를 유지할게요.",
    )
