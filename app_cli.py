"""
app_cli.py — 터미널 데모 (설계서 2.2 동작 흐름 전체를 손으로 따라가 보기)

실행:
    cd 0909-0911_langchain
    python -m newslingo.app_cli

강의 [4] Basic Agent "1-4. 챗봇" 의 `while True` 대화 루프 스타일.
UI 가 붙기 전까지 이 파일로 전체 플로우를 시연/검증한다.
"""

from __future__ import annotations

import json

from .service import LearningSession


def _pick(prompt: str, options: list[str]) -> str:
    while True:
        choice = input(f"{prompt} {options}: ").strip()
        if choice in options:
            return choice
        print("  → 목록 중에서 골라주세요.")


def main() -> None:
    print("=" * 60)
    session = LearningSession(user_id="cli_user")
    print(session.onboarding_message())

    # 0단계: 온보딩
    level = _pick("난이도 선택", ["초급", "중급", "고급"])
    session.set_initial_level(level)
    print(f"→ 현재 프로필: {session.profile}\n")

    # 1~2단계: 주제 요청 + 가드레일
    while True:
        topic_req = input("무엇을 공부하고 싶나요? > ").strip()
        guard = session.request_topic(topic_req)
        if guard.allowed:
            topic = guard.extracted_topic or topic_req
            print(f"→ 가드레일 통과. 추출 주제: {topic}\n")
            break
        print(f"⛔ {session.block_message(guard)}\n")

    # 3~4단계: 기사 5개 추천
    candidates = session.recommend_articles(topic)
    for i, art in enumerate(candidates.articles, 1):
        print(f"  [{i}] {art.title}  ({art.source}, {art.published_date})")
        print(f"      {art.summary}")
    idx = int(_pick("기사 선택", [str(i) for i in range(1, len(candidates.articles) + 1)]))

    # 5~6단계: 기사 선택 + 학습자료
    session.select_article(candidates.articles[idx - 1])
    material = session.make_study_material()
    print("\n--- 학습자료 ---")
    print("[원문]", material.original_text)
    print("[번역]", material.translated_text)
    print("[전문용어]", ", ".join(t.term for t in material.key_terms))
    print("[기본단어]", ", ".join(t.term for t in material.basic_vocab))
    print("[문법]", "; ".join(g.pattern for g in material.grammar_points))

    # 7단계: 자유 채팅 (exit 로 종료)
    print("\n--- 채팅 학습 (종료: exit) ---")
    while True:
        msg = input("나 > ").strip()
        if msg.lower() in {"exit", "quit", "끝", "끝내기"}:
            break
        out = session.chat(msg)
        if out["interrupt"] is not None:
            print("🔔 HITL:", out["interrupt"])
            approve = input("   변경을 승인할까요? (y/n) > ").strip().lower() == "y"
            out = session.confirm_preference(approve)
        print("튜터 >", out["reply"], "\n")

    # 8~9단계: 퀴즈 생성
    quiz = session.make_quiz()
    answers: list[str] = []
    print("\n--- 퀴즈 5문항 ---")
    for i, q in enumerate(quiz.questions, 1):
        print(f"Q{i}. {q.question}")
        for c in q.choices:
            print(f"   - {c}")
        answers.append(input("   내 답 > ").strip())

    # 10~11단계: 채점 + 난이도 추천
    result, recommendation = session.grade(answers)
    print(f"\n채점: {result.correct}/{result.total}  (정답률 {result.accuracy:.0%})")
    print("추천:", recommendation.message)

    # 12~14단계: 난이도 조정 (1차 선택 → HITL 2차 재확인)
    if recommendation.is_change():
        first = _pick("난이도 조정", ["상향", "하향", "유지"])
        if first in {"상향", "하향"}:
            out = session.propose_level_change(recommendation)
            if out["interrupt"] is not None:
                print("🔔 HITL:", out["interrupt"])
                approve = input("   정말 변경할까요? (y/n) > ").strip().lower() == "y"
                out = session.confirm_preference(approve)
            print("튜터 >", out["reply"])

    print(f"\n최종 프로필: {session.profile}")
    print("=" * 60)


if __name__ == "__main__":
    main()
