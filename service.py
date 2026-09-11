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
        self.unread_candidates = [
            a for a in self.unread_candidates if a.url != article.url
        ]

    def make_study_material(self) -> ArticleStudyMaterial:
        self._require_article()
        return study_material_chain.invoke(
            {
                "level": self.profile["level"],
                "article_title": self.current_article["title"],
                "article_text": self.current_article["text"],
            }
        )

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
            context=Context(user_id=self.user_id),
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
            context=Context(user_id=self.user_id),
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
    def propose_level_change(self, recommendation: LevelRecommendation) -> dict:
        """사용자가 상/하/유지 버튼을 1차 선택했을 때 호출.

        'keep' 이면 아무 것도 하지 않고, 변경이면 Agent 에게 update_preference 를
        요청 → HITL 이 2차 재확인 interrupt 를 띄운다.
        """
        if not recommendation.is_change():
            return {"reply": recommendation.message, "interrupt": None}
        return self.chat(
            f"난이도를 '{recommendation.suggested_level}'(으)로 변경해줘. "
            f"update_preference Tool 을 사용해."
        )

    # ──────────────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────────────
    def _require_article(self) -> None:
        if self.current_article is None:
            raise RuntimeError("먼저 select_article() 로 기사를 선택하세요.")

    def _unpack(self, result: dict) -> dict:
        interrupts = result.get("__interrupt__")
        if interrupts:
            return {"reply": None, "interrupt": interrupts[0].value}
        reply = result["messages"][-1].content
        if reply:
            self.chat_log.append(f"Tutor: {reply}")
        return {"reply": reply, "interrupt": None}
