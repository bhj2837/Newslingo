"""
service.py — 상위 오케스트레이션 (설계서 2.2 동작 흐름)

UI / CLI / 데모 노트북은 이 파일의 `LearningSession` 하나만 알면 된다.
설계서 2.2 의 1~15단계를 메서드로 1:1 대응시켰다.

세션 임시 State (설계서 3.1):
  - current_article      : 사용자가 선택한 기사
  - chat_log             : 채팅 중 나눈 대화(퀴즈 근거)
  - unread_candidates    : 아직 안 읽은 추천 기사
  - seen_article_urls    : 세션 중 보여준 모든 기사 URL
장기 State 는 Store 의 profile(topic, level).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from langgraph.types import Command

from . import config
from .agent import Context, build_agent
from .chains import article_recommender_chain, quiz_chain, study_material_chain
from .grading import grade_quiz, recommend_level
from .guardrails import check_topic
from .memory import Profile, get_store, load_profile, save_profile
from .prompts import GUARDRAIL_BLOCK_MESSAGE, ONBOARDING_MESSAGE
from .schemas import (
    ArticleCandidate,
    ArticleCandidateList,
    ArticleStudyMaterial,
    LevelRecommendation,
    QuizResult,
    QuizSet,
    TopicGuardrailResult,
)
from .tools import news_search

# ──────────────────────────────────────────────────────────────
# 채팅 중 "다른 기사"/"그만 할래" 같은 제어 의도 감지 (규칙 기반, 문제 5/6/7)
#
# 예전엔 이런 문구도 그냥 채팅 Agent에게 넘겨서 Tool-calling으로 처리하려 했는데,
#   - "다른 기사"류 → news_search 를 반복 호출하다 recursion limit 크래시
#   - "그만할래"류 → update_preference(level 변경)로 잘못 해석돼 엉뚱한 HITL 발생
# 두 경우 다 LLM 판단에 맡기면 오류가 잦아서, 이건 아예 Agent 에게 보내지 않고
# 여기서 규칙 기반으로만 감지한다. 실제 전환은 UI 버튼(app_cli.py 의 'n'/'q')으로만
# 하고, 여기서 감지되면 "버튼을 눌러주세요" 안내만 돌려준다.
# ──────────────────────────────────────────────────────────────
_NEXT_ARTICLE_PATTERNS = (
    "다른 기사", "다른기사", "다음 기사", "다음기사", "다른 뉴스", "다른뉴스",
)
_END_STUDY_PATTERNS = (
    "그만할래", "그만할게", "그만볼래", "끝낼래", "끝낼게", "그만 공부", "공부 그만",
    "공부 끝", "학습 종료", "학습종료", "종료할래",
)


@dataclass
class LearningSession:
    """한 명의 사용자, 한 번의 학습 세션."""

    user_id: str
    thread_id: str = field(default_factory=lambda: f"thread-{uuid.uuid4().hex[:8]}")

    # 세션 임시 State
    current_article: dict | None = None
    chat_log: list[str] = field(default_factory=list)
    unread_candidates: list[ArticleCandidate] = field(default_factory=list)
    seen_article_urls: set[str] = field(default_factory=set)
    last_quiz: QuizSet | None = None
    study_material: ArticleStudyMaterial | None = None  # 2-a: chat()에서 Context로 주입하려고 캐시

    def __post_init__(self) -> None:
        self._agent = build_agent()
        self._store = get_store()

    # ──────────────────────────────────────────────────────
    # 0단계. 온보딩 — 최초 난이도 선택 (설계서 1.3 시나리오 1)
    # ──────────────────────────────────────────────────────
    @staticmethod
    def onboarding_message() -> str:
        return ONBOARDING_MESSAGE

    @property
    def profile(self) -> Profile:
        return load_profile(self._store, self.user_id)

    def set_initial_level(self, level: str) -> Profile:
        """최초 접속 시 사용자가 직접 고른 난이도를 저장한다 (HITL 없이 직접 반영)."""
        if level not in config.LEVELS:
            raise ValueError(f"난이도는 {config.LEVELS} 중 하나여야 합니다.")
        return save_profile(self._store, self.user_id, level=level)

    # ──────────────────────────────────────────────────────
    # 1~2단계. 입력 가드레일 (설계서 3.3)
    # ──────────────────────────────────────────────────────
    def request_topic(self, user_text: str) -> TopicGuardrailResult:
        """학습 주제 요청을 2단계 가드레일에 통과시킨다."""
        return check_topic(user_text)

    @staticmethod
    def block_message(result: TopicGuardrailResult) -> str:
        reason = f" ({result.block_reason})" if result.block_reason else ""
        return f"{GUARDRAIL_BLOCK_MESSAGE}{reason}"

    # ──────────────────────────────────────────────────────
    # 3~4단계. 기사 검색 + 5개 추천 (설계서 2.2, 테스트 TS-01/TS-09)
    # ──────────────────────────────────────────────────────
    def recommend_articles(self, topic: str) -> ArticleCandidateList:
        """news_search Tool → article_recommender_chain 으로 기사 5개를 만든다.

        seen_article_urls 를 exclude 로 넘겨 이미 본 기사는 제외한다 (설계서 2.5).
        """
        raw = news_search.invoke(
            {"query": topic, "exclude_urls": sorted(self.seen_article_urls)}
        )
        payload = json.loads(raw)
        raw_articles = payload.get("articles", [])

        candidate_list: ArticleCandidateList = article_recommender_chain.invoke(
            {
                "topic": topic,
                "level": self.profile["level"],
                "seen_urls": sorted(self.seen_article_urls) or "(없음)",
                "raw_articles": json.dumps(raw_articles, ensure_ascii=False),
            }
        )

        # 원문 본문을 URL 로 찾아둘 수 있게 매핑 저장
        self._raw_by_url = {a["url"]: a for a in raw_articles}
        self.unread_candidates = list(candidate_list.articles)
        self.seen_article_urls.update(a.url for a in candidate_list.articles)
        return candidate_list

    def list_unread(self) -> list[ArticleCandidate]:
        """15-A단계: 재검색 없이 남은 후보 재표시 (설계서 2.2, 테스트 TS-09)."""
        return list(self.unread_candidates)

    # ──────────────────────────────────────────────────────
    # 5~6단계. 기사 선택 + 학습자료 생성 (설계서 2.2)
    # ──────────────────────────────────────────────────────
    def select_article(self, article: ArticleCandidate) -> None:
        raw = getattr(self, "_raw_by_url", {}).get(article.url, {})
        self.current_article = {
            "title": article.title,
            "url": article.url,
            "text": raw.get("content") or article.summary,
        }
        self.chat_log = []
        self.study_material = None  # 새 기사로 바뀌면 이전 학습자료는 더 이상 유효하지 않음
        self.unread_candidates = [
            a for a in self.unread_candidates if a.url != article.url
        ]

    def make_study_material(self) -> ArticleStudyMaterial:
        self._require_article()
        material = study_material_chain.invoke(
            {
                "level": self.profile["level"],
                "article_title": self.current_article["title"],
                "article_text": self.current_article["text"],
            }
        )
        self.study_material = material  # 2-a: chat()에서 Agent 에게 주입할 수 있게 캐시
        return material

    # ──────────────────────────────────────────────────────
    # 6-B. 채팅 자유 텍스트의 제어 의도 감지 (문제 5/6/7, 규칙 기반)
    # ──────────────────────────────────────────────────────
    @staticmethod
    def detect_control_intent(text: str) -> str | None:
        """"다른 기사"/"그만할래" 같은 문구를 채팅 Agent 로 보내기 전에 걸러낸다.

        Returns:
            "next_article" / "end_study" / None (제어 의도 아님 → 평소처럼 chat() 호출)
        이 메서드는 아무 것도 실행하지 않는다 — 호출부(UI/CLI)가 감지 결과를 보고
        "버튼을 눌러주세요"라고 안내하거나, 직접 버튼 액션을 트리거해야 한다.
        """
        stripped = text.strip()
        if any(p in stripped for p in _NEXT_ARTICLE_PATTERNS):
            return "next_article"
        if any(p in stripped for p in _END_STUDY_PATTERNS):
            return "end_study"
        return None

    # ──────────────────────────────────────────────────────
    # 7단계. 자유 채팅 학습 지원 (설계서 2.2, 테스트 TS-05/TS-06)
    # ──────────────────────────────────────────────────────
    def chat(self, message: str) -> dict:
        """메인 Agent 와 대화한다.

        Returns:
            {"reply": str, "interrupt": <HITL 요청 or None>}
            interrupt 가 있으면 update_preference 승인 대기 상태다 → confirm_preference() 호출.
        """
        self.chat_log.append(f"User: {message}")
        result = self._agent.invoke(
            {"messages": [{"role": "user", "content": message}]},
            config={
                "configurable": {"thread_id": self.thread_id},
                "recursion_limit": 2 * config.TOOL_CALL_LIMIT + 3,
            },
            context=self._build_context(),
        )
        return self._unpack(result)

    def confirm_preference(self, approve: bool, message: str | None = None) -> dict:
        """HITL 2차 재확인에 응답한다 (설계서 3.3, 테스트 TS-06/TS-08-C002).

        approve=False 면 Tool 이 실행되지 않아 기존 Store 값이 그대로 유지된다.
        """
        decision = (
            {"type": "approve"}
            if approve
            else {"type": "reject", "message": message or "사용자가 변경을 취소했습니다."}
        )
        result = self._agent.invoke(
            Command(resume={"decisions": [decision]}),
            config={"configurable": {"thread_id": self.thread_id}},
            context=self._build_context(),
        )
        return self._unpack(result)

    # ──────────────────────────────────────────────────────
    # 8~9단계. 끝내기 / 다른기사 탐색 → 퀴즈 생성 (공통, 테스트 TS-07)
    # ──────────────────────────────────────────────────────
    def make_quiz(self) -> QuizSet:
        self._require_article()
        quiz: QuizSet = quiz_chain.invoke(
            {
                "level": self.profile["level"],
                "article_text": self.current_article["text"],
                "chat_log": "\n".join(self.chat_log) or "(대화 없음)",
            }
        )
        self.last_quiz = quiz
        return quiz

    # ──────────────────────────────────────────────────────
    # 10~11단계. 채점 + 난이도 추천 (설계서 2.2, 테스트 TS-08)
    # ──────────────────────────────────────────────────────
    def grade(self, user_answers: list[str]) -> tuple[QuizResult, LevelRecommendation]:
        if self.last_quiz is None:
            raise RuntimeError("먼저 make_quiz() 로 퀴즈를 생성하세요.")
        result = grade_quiz(self.last_quiz, user_answers)
        recommendation = recommend_level(result.accuracy, self.profile["level"])
        return result, recommendation

    # ──────────────────────────────────────────────────────
    # 12~14단계. 난이도 조정 (1차 선택 → HITL 2차 재확인)
    # ──────────────────────────────────────────────────────
    def request_level_change(self, target_level: str) -> dict:
        """사용자가 상/하/유지 버튼으로 '직접 고른' 난이도로 변경을 요청한다.

        예전 propose_level_change(recommendation) 은 시스템 추천이 'keep'이면
        무조건 아무 것도 안 해서, 추천이 '유지'로 나와도 사용자가 그와 무관하게
        상향/하향을 직접 선택할 수 있어야 한다는 요구를 반영 못 했다. 이제는
        추천 방향과 무관하게, 사용자가 실제로 고른 target_level 을 그대로 받아서
        현재 값과 다를 때만 update_preference(HITL 2차 재확인)를 태운다.
        """
        if target_level not in config.LEVELS:
            raise ValueError(f"난이도는 {config.LEVELS} 중 하나여야 합니다.")
        if target_level == self.profile["level"]:
            return {"reply": f"현재 '{target_level}' 난이도를 유지할게요.", "interrupt": None}
        return self.chat(
            f"난이도를 '{target_level}'(으)로 변경해줘. update_preference Tool 을 사용해."
        )

    # ──────────────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────────────
    def _require_article(self) -> None:
        if self.current_article is None:
            raise RuntimeError("먼저 select_article() 로 기사를 선택하세요.")

    def _build_context(self) -> Context:
        """agent.invoke(context=...) 에 넘길 Context 를 매 호출마다 새로 만든다.

        2-a 수정: 현재 선택된 기사 원문 + (있으면) 학습자료 요약을 담아서
        middleware.profile_injection 이 system prompt 에 주입할 수 있게 한다.
        기사를 아직 안 골랐으면 article_* 는 빈 문자열로 남아 기존 동작과 동일.
        """
        if self.current_article is None:
            return Context(user_id=self.user_id)
        return Context(
            user_id=self.user_id,
            article_title=self.current_article["title"],
            article_text=self.current_article["text"],
            study_material_summary=self._material_summary(),
        )

    def _material_summary(self) -> str:
        """study_material 캐시를 system prompt 에 넣기 좋은 텍스트 블록으로 정리."""
        material = self.study_material
        if material is None:
            return ""

        lines = [f"번역:\n{material.translated_text}", "", "전문 용어:"]
        lines += [f"- {t.term} ({t.meaning}): {t.example}" for t in material.key_terms]
        lines += ["", "기본 단어:"]
        lines += [f"- {t.term} ({t.meaning}): {t.example}" for t in material.basic_vocab]
        lines += ["", "문법 포인트:"]
        lines += [
            f"- {g.pattern}: {g.explanation}\n  예문: {g.example}"
            for g in material.grammar_points
        ]
        return "\n".join(lines)

    def _unpack(self, result: dict) -> dict:
        interrupts = result.get("__interrupt__")
        if interrupts:
            return {"reply": None, "interrupt": interrupts[0].value}
        reply = result["messages"][-1].content
        if reply:
            self.chat_log.append(f"Tutor: {reply}")
        return {"reply": reply, "interrupt": None}
