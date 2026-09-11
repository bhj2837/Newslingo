"""
test_logic.py — LLM 호출 없이 검증 가능한 부분만 테스트 (설계서 4. 테스트 설계)

실행:  cd 0909-0911_langchain && python -m pytest newslingo/tests -q
(pytest 없으면:  python newslingo/tests/test_logic.py )
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from newslingo import config
from newslingo.grading import grade_quiz, recommend_level
from newslingo.guardrails import rule_based_filter
from newslingo.schemas import QuizQuestion, QuizSet


def _dummy_quiz() -> QuizSet:
    return QuizSet(
        questions=[
            QuizQuestion(
                question=f"문제 {i}",
                choices=["A", "B", "C", "D"],
                answer="A",
                explanation="해설",
            )
            for i in range(5)
        ]
    )


# TS-02 : 금칙어 요청이 1차 규칙 필터에서 즉시 차단 (모델 호출 없음)
def test_ts02_rule_filter_blocks_banned_word():
    result = rule_based_filter("야한 뉴스 보여줘")
    assert result is not None and result.allowed is False


def test_ts02_rule_filter_passes_normal_request():
    assert rule_based_filter("반도체 산업 뉴스로 공부하고 싶어") is None


# TS-07 : QuizSet 은 정확히 5문항, 각 4지선다
def test_ts07_quiz_schema_shape():
    quiz = _dummy_quiz()
    assert len(quiz.questions) == 5
    assert all(len(q.choices) == 4 for q in quiz.questions)


# TS-08 : 정답률 80% 경계에서 '상향' 추천
def test_ts08_boundary_80_percent_recommends_up():
    quiz = _dummy_quiz()
    graded = grade_quiz(quiz, ["A", "A", "A", "A", "B"])  # 4/5 = 80%
    assert graded.accuracy == 0.8
    rec = recommend_level(graded.accuracy, "중급")
    assert rec.direction == "up" and rec.suggested_level == "고급"


def test_ts08_low_accuracy_recommends_down():
    rec = recommend_level(0.2, "중급")
    assert rec.direction == "down" and rec.suggested_level == "초급"


def test_level_stays_when_no_room_to_move():
    assert recommend_level(1.0, "고급").direction == "keep"
    assert recommend_level(0.0, "초급").direction == "keep"


# 채점 로직: 대소문자/공백 차이를 무시
def test_grade_is_case_insensitive():
    quiz = _dummy_quiz()
    graded = grade_quiz(quiz, [" a ", "a", "A", "A", "A"])
    assert graded.correct == 5


# update_preference 유효성: 잘못된 level 은 저장 로직에 도달하기 전에 거부
def test_invalid_level_rejected():
    from newslingo.tools import update_preference

    try:
        update_preference.func(runtime=None, level="왕초보")  # type: ignore[arg-type]
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("잘못된 level 인데 ValueError 가 발생하지 않음")


def test_levels_constant():
    assert config.LEVELS == ("초급", "중급", "고급")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok:", fn.__name__)
    print(f"\n{len(fns)} passed")
