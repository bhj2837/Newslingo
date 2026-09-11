"""
app_cli.py — 터미널 데모 (설계서 2.2 동작 흐름 전체를 손으로 따라가 보기)

실행:
    cd 0909-0911_langchain
    python -m newslingo.app_cli

강의 [4] Basic Agent "1-4. 챗봇" 의 `while True` 대화 루프 스타일.
UI 가 붙기 전까지 이 파일로 전체 플로우를 시연/검증한다.
"""

from __future__ import annotations

from . import config
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

    # 3~4단계: 기사 5개 추천 (최초 1회)
    candidates = session.recommend_articles(topic).articles

    # 5~14단계: 기사 선택 → 학습자료 → 채팅 → 퀴즈 → 채점/난이도 조정을 기사
    # 단위로 반복한다. n(다른 기사)/q(학습 종료) 둘 다 "이 기사에서 넘어간다"는
    # 신호일 뿐이고, 어느 쪽이든 넘어가기 전에 반드시 퀴즈를 본다 — 예전엔 n을
    # 누르면 퀴즈 없이 바로 다음 기사로 넘어가버렸는데, 그러면 방금 읽은 기사에
    # 대한 학습 점검이 통째로 빠지므로 이제는 무조건 퀴즈를 거치게 바꿨다.
    while True:
        for i, art in enumerate(candidates, 1):
            print(f"  [{i}] {art.title}  ({art.source}, {art.published_date})")
            print(f"      {art.summary}")
        idx = int(_pick("기사 선택", [str(i) for i in range(1, len(candidates) + 1)]))

        # 5~6단계: 기사 선택 + 학습자료
        session.select_article(candidates[idx - 1])
        material = session.make_study_material()
        print("\n--- 학습자료 ---")
        print("[원문]")
        print(material.original_text)
        print("\n[번역]")
        print(material.translated_text)

        print("\n[전문용어]")
        for t in material.key_terms:
            print(f"  - {t.term} : {t.meaning}")
            print(f"      예문) {t.example}")

        print("\n[기본단어]")
        for t in material.basic_vocab:
            print(f"  - {t.term} : {t.meaning}")
            print(f"      예문) {t.example}")

        print("\n[문법]")
        for g in material.grammar_points:
            print(f"  - {g.pattern}")
            print(f"      설명) {g.explanation}")
            print(f"      예문) {g.example}")

        # 7단계: 자유 채팅
        print("\n--- 채팅 학습 ---")
        print("[버튼]  다른 기사 보기: n   |   학습 종료: q\n")
        leaving = False
        while not leaving:
            msg = input("나 > ").strip()
            if msg.lower() in {"q", "exit", "quit", "끝", "끝내기", "n", "다음", "다음기사", "다른기사"}:
                leaving = True
                continue

            # 문제 5/6/7: "다른 기사"/"그만할래" 같은 자연어는 Agent(LLM)에게
            # 넘기지 않고 규칙 기반으로만 감지해서 버튼 사용을 안내한다.
            intent = LearningSession.detect_control_intent(msg)
            if intent == "next_article":
                print("튜터 > 다른 기사를 보고 싶으시면 위의 [다른 기사 보기: n] 버튼을 눌러주세요.\n")
                continue
            if intent == "end_study":
                print("튜터 > 학습을 끝내고 싶으시면 위의 [학습 종료: q] 버튼을 눌러주세요.\n")
                continue

            out = session.chat(msg)
            if out["interrupt"] is not None:
                print("🔔 HITL:", out["interrupt"])
                approve = input("   변경을 승인할까요? (y/n) > ").strip().lower() == "y"
                out = session.confirm_preference(approve)
            print("튜터 >", out["reply"], "\n")

        want_end_study = msg.lower() in {"q", "exit", "quit", "끝", "끝내기"}

        # 8~9단계: 이 기사에 대한 퀴즈 (n/q 상관없이 항상 실행)
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

        # 12~14단계: 난이도 조정 — 추천이 '유지'여도 사용자가 직접 상/하향을
        # 고를 수 있어야 하므로, 추천 방향과 무관하게 항상 물어본다 (1차 선택 → HITL 2차 재확인)
        current_level = session.profile["level"]
        current_idx = config.LEVELS.index(current_level)
        choice = _pick(f"난이도 조정 (추천: {recommendation.message})", ["상향", "하향", "유지"])
        if choice == "상향" and current_idx < len(config.LEVELS) - 1:
            target_level = config.LEVELS[current_idx + 1]
        elif choice == "하향" and current_idx > 0:
            target_level = config.LEVELS[current_idx - 1]
        else:
            target_level = current_level  # '유지' 선택, 또는 이미 최상급/최하급

        out = session.request_level_change(target_level)
        if out["interrupt"] is not None:
            print("🔔 HITL:", out["interrupt"])
            approve = input("   정말 변경할까요? (y/n) > ").strip().lower() == "y"
            out = session.confirm_preference(approve)
        print("튜터 >", out["reply"])

        if want_end_study:
            break

        unread = session.list_unread()
        candidates = unread if unread else session.recommend_articles(topic).articles
        if not candidates:
            print("→ 더 이상 추천할 기사가 없어요. 학습을 종료합니다.\n")
            break
        print()

    print(f"\n최종 프로필: {session.profile}")
    print("=" * 60)


if __name__ == "__main__":
    main()
