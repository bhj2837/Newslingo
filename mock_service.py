"""
mock_service.py — API 키 없이 UI만 확인할 때 쓰는 목업 세션

LearningSession(service.py) 과 완전히 동일한 public 인터페이스를 가진 대체 구현.
LLM/News API를 전혀 호출하지 않고 고정된 샘플 데이터로 응답한다.
grading.py(순수 파이썬 채점 로직)만 실제 로직을 그대로 재사용한다.

app.py 에서 OPENAI_API_KEY 가 없을 때 LearningSession 대신 이 클래스를 쓴다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from . import config
from .grading import grade_quiz, recommend_level
from .schemas import (
    ArticleCandidate,
    ArticleCandidateList,
    ArticleStudyMaterial,
    GrammarItem,
    LevelRecommendation,
    QuizQuestion,
    QuizResult,
    QuizSet,
    TermItem,
    TopicGuardrailResult,
)

ONBOARDING_MESSAGE_MOCK = (
    "안녕하세요! 뉴스링고에 오신 걸 환영해요 🎓\n"
    "먼저 지금 영어 실력이 어느 정도인지 골라주세요."
)

_BLOCK_MESSAGE = "죄송해요, 그 주제로는 학습 자료를 만들어드리기 어려워요."

# 데스크톱/모바일 목업과 동일한 5개 샘플 기사 — 디자인 시안과 내용을 맞춰 데모 일관성을 유지한다.
_SAMPLE_ARTICLES: list[dict] = [
    {
        "title": "AI Regulation Bill Clears Senate Committee",
        "source": "The Verge",
        "date": "2026-09-09",
        "tag": "Technology",
        "keywords": ["AI", "regulation", "policy"],
        "summary": "A sweeping AI regulation bill advanced out of committee this week.",
        "text": (
            "A sweeping bill to regulate artificial intelligence systems advanced out of "
            "committee on Tuesday, marking the most significant legislative push yet to "
            "rein in the rapidly growing technology.\n\n"
            "The measure would require companies developing large-scale AI models to "
            "submit safety assessments before public release, and establishes a new "
            "federal office to oversee compliance. Industry groups warned the rules "
            "could slow innovation."
        ),
        "translation": (
            "인공지능 시스템을 규제하는 대규모 법안이 화요일 위원회를 통과하며, 빠르게 성장하는 "
            "이 기술을 통제하려는 가장 중요한 입법 시도로 평가받고 있다.\n\n"
            "이 법안은 대규모 AI 모델을 개발하는 기업들이 공개 이전에 안전성 평가를 제출하도록 "
            "요구하며, 준수 여부를 감독할 새로운 연방 기구를 신설한다. 업계 단체들은 이 규제가 "
            "혁신 속도를 늦출 수 있다고 우려했다."
        ),
        "key_terms": [
            ("rein in", "억제하다, 통제하다", "The new law aims to rein in AI risks."),
            ("compliance", "준수, 이행", "The office oversees compliance with the rules."),
            ("sweeping", "광범위한", "It is a sweeping reform of AI policy."),
        ],
        "basic_vocab": [
            ("advance", "진전하다, 통과되다", "The bill advanced out of committee."),
            ("require", "요구하다", "The law requires safety assessments."),
        ],
        "grammar": ("would require + 명사 + to부정사", "법안·규정이 '~하도록 요구할 것이다'라는 표현."),
    },
    {
        "title": "Arctic Sea Ice Hits Second-Lowest Level",
        "source": "Reuters",
        "date": "2026-09-08",
        "tag": "Climate",
        "keywords": ["climate", "arctic", "ice"],
        "summary": "Arctic sea ice extent has dropped to its second-lowest level on record.",
        "text": (
            "Arctic sea ice extent shrank to its second-lowest level on record this "
            "summer, scientists reported Monday, underscoring the accelerating pace of "
            "climate change in the polar region.\n\n"
            "Researchers said warmer ocean currents and prolonged heat waves contributed "
            "to the melt, which could disrupt shipping routes and wildlife habitats."
        ),
        "translation": (
            "과학자들은 월요일, 북극 해빙 면적이 이번 여름 관측 사상 두 번째로 낮은 수준까지 "
            "줄어들었다고 발표하며 극지방의 기후 변화가 가속화되고 있음을 보여준다고 밝혔다.\n\n"
            "연구자들은 따뜻해진 해류와 장기간 이어진 폭염이 해빙 감소의 원인이라고 설명했으며, "
            "이는 선박 항로와 야생동물 서식지에 영향을 줄 수 있다고 덧붙였다."
        ),
        "key_terms": [
            ("extent", "범위, 크기", "The extent of the ice sheet has shrunk."),
            ("underscore", "강조하다, 부각시키다", "This underscores the urgency of the issue."),
            ("disrupt", "방해하다, 지장을 주다", "Melting ice could disrupt shipping routes."),
        ],
        "basic_vocab": [
            ("shrink", "줄어들다", "The ice extent shrank this year."),
            ("prolonged", "장기간의", "A prolonged heat wave hit the region."),
        ],
        "grammar": ("could + 동사원형 (추측/가능성)", "'~할 수도 있다'는 가능성을 나타내는 표현."),
    },
    {
        "title": "NASA Delays Artemis III Crewed Landing",
        "source": "AP News",
        "date": "2026-09-07",
        "tag": "Space",
        "keywords": ["NASA", "Artemis", "space"],
        "summary": "NASA has pushed back the timeline for its next crewed Moon landing.",
        "text": (
            "NASA announced Thursday that its Artemis III mission, intended to return "
            "astronauts to the lunar surface, will be delayed due to ongoing hardware "
            "and software testing issues.\n\n"
            "Officials said the extra time would be used to ensure the safety of the "
            "crew and the reliability of the lunar lander system."
        ),
        "translation": (
            "NASA는 목요일, 우주비행사들을 달 표면으로 복귀시키려는 아르테미스 3호 임무가 진행 중인 "
            "하드웨어 및 소프트웨어 시험 문제로 인해 연기될 것이라고 발표했다.\n\n"
            "관계자들은 추가된 시간이 승무원의 안전과 달 착륙선 시스템의 신뢰성을 확보하는 데 "
            "쓰일 것이라고 밝혔다."
        ),
        "key_terms": [
            ("crewed", "유인의", "This is a crewed mission to the Moon."),
            ("reliability", "신뢰성", "Engineers are testing the lander's reliability."),
            ("hardware", "하드웨어, 장비", "The delay is due to hardware issues."),
        ],
        "basic_vocab": [
            ("delay", "연기하다, 지연시키다", "NASA delayed the launch."),
            ("ensure", "보장하다, 확실히 하다", "They want to ensure crew safety."),
        ],
        "grammar": ("intended to + 동사원형", "'~하기 위해 의도된, ~할 목적의'라는 표현."),
    },
    {
        "title": "Central Bank Signals Rate Pause Ahead",
        "source": "Bloomberg",
        "date": "2026-09-09",
        "tag": "Economy",
        "keywords": ["economy", "interest rate", "bank"],
        "summary": "The central bank hinted it may hold interest rates steady next quarter.",
        "text": (
            "The central bank signaled Wednesday that it may pause interest rate hikes "
            "next quarter, citing signs that inflation is beginning to cool.\n\n"
            "Analysts said the shift in tone suggests policymakers are growing more "
            "confident that the economy can avoid a sharp slowdown."
        ),
        "translation": (
            "중앙은행은 수요일, 인플레이션이 진정되는 조짐을 보인다며 다음 분기에는 금리 인상을 "
            "멈출 수도 있다는 신호를 보냈다.\n\n"
            "분석가들은 이러한 어조 변화가 경제가 급격한 둔화를 피할 수 있다는 정책 입안자들의 "
            "자신감이 커지고 있음을 시사한다고 말했다."
        ),
        "key_terms": [
            ("signal", "암시하다, 신호를 보내다", "The bank signaled a possible pause."),
            ("cool", "진정되다, 식다", "Inflation is beginning to cool."),
            ("policymaker", "정책 입안자", "Policymakers are watching inflation closely."),
        ],
        "basic_vocab": [
            ("pause", "멈추다, 중단하다", "The bank may pause rate hikes."),
            ("confident", "자신감 있는", "They feel more confident about the economy."),
        ],
        "grammar": ("citing + 명사 (근거 제시)", "'~을 근거로 들며'라는 뜻으로 이유를 덧붙일 때 쓰는 표현."),
    },
    {
        "title": "New Study Links Sleep Patterns to Memory",
        "source": "NPR",
        "date": "2026-09-06",
        "tag": "Health",
        "keywords": ["health", "sleep", "memory"],
        "summary": "A new study finds a strong link between sleep quality and memory retention.",
        "text": (
            "A new study published this week found that people who get consistent, "
            "high-quality sleep retain new information significantly better than those "
            "with irregular sleep patterns.\n\n"
            "Researchers tracked participants over six months and found that deep sleep "
            "stages play a key role in consolidating memories."
        ),
        "translation": (
            "이번 주 발표된 새로운 연구에 따르면, 일관되고 질 좋은 수면을 취하는 사람들이 수면이 "
            "불규칙한 사람들보다 새로운 정보를 훨씬 더 잘 기억하는 것으로 나타났다.\n\n"
            "연구자들은 참가자들을 6개월간 추적 관찰했으며, 깊은 수면 단계가 기억을 정착시키는 데 "
            "핵심적인 역할을 한다는 것을 발견했다."
        ),
        "key_terms": [
            ("retain", "유지하다, 기억하다", "They retain information better after good sleep."),
            ("consolidate", "굳히다, 공고히 하다", "Deep sleep helps consolidate memories."),
            ("irregular", "불규칙한", "Irregular sleep hurts memory performance."),
        ],
        "basic_vocab": [
            ("track", "추적하다", "Researchers tracked participants for months."),
            ("consistent", "일관된", "Consistent sleep improves memory."),
        ],
        "grammar": ("those with + 명사 (~을 가진 사람들)", "'~을 가진/한 사람들'이라는 뜻으로 대상을 지칭하는 표현."),
    },
]


@dataclass
class MockLearningSession:
    """LearningSession 과 동일한 인터페이스를 가진 목업 세션 (API 키 불필요)."""

    user_id: str
    thread_id: str = field(default_factory=lambda: f"mock-thread-{uuid.uuid4().hex[:8]}")

    current_article: dict | None = None
    chat_log: list[str] = field(default_factory=list)
    unread_candidates: list[ArticleCandidate] = field(default_factory=list)
    last_quiz: QuizSet | None = None

    def __post_init__(self) -> None:
        self._profile = {"topic": config.DEFAULT_TOPIC, "level": config.DEFAULT_LEVEL}
        self._article_by_url: dict[str, dict] = {}
        self._pending_level_change: str | None = None

    # ── 0단계: 온보딩 ──────────────────────────────────────────
    @staticmethod
    def onboarding_message() -> str:
        return ONBOARDING_MESSAGE_MOCK

    @property
    def profile(self) -> dict:
        return dict(self._profile)

    def set_initial_level(self, level: str) -> dict:
        if level not in config.LEVELS:
            raise ValueError(f"난이도는 {config.LEVELS} 중 하나여야 합니다.")
        self._profile["level"] = level
        return self.profile

    # ── 1~2단계: 가드레일 (항상 통과) ──────────────────────────
    def request_topic(self, user_text: str) -> TopicGuardrailResult:
        text = user_text.strip()
        if not text:
            return TopicGuardrailResult(allowed=False, block_reason="주제를 입력해주세요.")
        return TopicGuardrailResult(allowed=True, extracted_topic=text)

    @staticmethod
    def block_message(result: TopicGuardrailResult) -> str:
        reason = f" ({result.block_reason})" if result.block_reason else ""
        return f"{_BLOCK_MESSAGE}{reason}"

    # ── 3~4단계: 기사 추천 (고정 샘플 5개) ─────────────────────
    def recommend_articles(self, topic: str) -> ArticleCandidateList:
        articles = []
        for i, raw in enumerate(_SAMPLE_ARTICLES):
            url = f"mock://article-{i}"
            self._article_by_url[url] = raw
            articles.append(
                ArticleCandidate(
                    title=raw["title"],
                    url=url,
                    summary=raw["summary"],
                    source=raw["source"],
                    published_date=raw["date"],
                    keywords=raw["keywords"],
                )
            )
        self.unread_candidates = list(articles)
        return ArticleCandidateList(articles=articles)

    def list_unread(self) -> list[ArticleCandidate]:
        return list(self.unread_candidates)

    # ── 5~6단계: 기사 선택 + 학습자료 ──────────────────────────
    def select_article(self, article: ArticleCandidate) -> None:
        raw = self._article_by_url.get(article.url, {})
        self.current_article = {
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "date": article.published_date,
            "text": raw.get("text", article.summary),
            "_raw": raw,
        }
        self.chat_log = []
        self.unread_candidates = [a for a in self.unread_candidates if a.url != article.url]

    def make_study_material(self) -> ArticleStudyMaterial:
        self._require_article()
        raw = self.current_article["_raw"]
        return ArticleStudyMaterial(
            translated_text=raw["translation"],
            key_terms=[TermItem(term=t, meaning=m, example=e) for t, m, e in raw["key_terms"]],
            basic_vocab=[
                TermItem(term=t, meaning=m, example=e)
                for t, m, e in (raw["basic_vocab"] * 2)[:3]
            ],
            grammar_points=[GrammarItem(pattern=raw["grammar"][0], explanation=raw["grammar"][1], example=raw["text"].split(".")[0] + ".")],
        )

    # ── 7단계: 채팅 (키워드 기반 고정 응답 + 목업 HITL) ────────
    def chat(self, message: str) -> dict:
        self.chat_log.append(f"User: {message}")
        lowered = message.lower()

        if any(k in lowered for k in ("난이도", "레벨", "level")):
            levels = config.LEVELS
            idx = levels.index(self._profile["level"])
            target = levels[min(idx + 1, len(levels) - 1)]
            self._pending_level_change = target
            return {"reply": None, "interrupt": f"난이도를 '{target}'(으)로 변경할까요? (목업 확인)"}

        for term, meaning, _ in self.current_article.get("_raw", {}).get("key_terms", []) if self.current_article else []:
            if term.lower() in lowered:
                reply = f"'{term}'은(는) '{meaning}'라는 뜻이에요. (목업 응답)"
                self.chat_log.append(f"Tutor: {reply}")
                return {"reply": reply, "interrupt": None}

        reply = "좋은 질문이에요! 지금은 목업 데이터 모드라 정해진 답변만 드릴 수 있어요. API 키를 연결하면 실제 튜터가 답해줄 거예요."
        self.chat_log.append(f"Tutor: {reply}")
        return {"reply": reply, "interrupt": None}

    def confirm_preference(self, approve: bool, message: str | None = None) -> dict:
        if approve and self._pending_level_change:
            self._profile["level"] = self._pending_level_change
            reply = f"난이도를 '{self._pending_level_change}'(으)로 변경했어요."
        else:
            reply = "변경을 취소했어요."
        self._pending_level_change = None
        self.chat_log.append(f"Tutor: {reply}")
        return {"reply": reply, "interrupt": None}

    # ── 8~9단계: 퀴즈 (기사별 고정 5문항) ──────────────────────
    def make_quiz(self) -> QuizSet:
        self._require_article()
        raw = self.current_article["_raw"]
        terms = raw["key_terms"] + raw["basic_vocab"]
        distract_pool = [m for _, m, _ in terms]

        questions: list[QuizQuestion] = []
        for term, meaning, example in terms[:4]:
            wrong = [m for m in distract_pool if m != meaning][:3]
            choices = [meaning, *wrong]
            questions.append(
                QuizQuestion(
                    question=f"'{term}'의 뜻으로 알맞은 것은?",
                    choices=choices,
                    answer=meaning,
                    explanation=f"'{term}'은(는) 이 기사에서 '{example}' 처럼 쓰였어요.",
                )
            )
        tags = [a["tag"] for a in _SAMPLE_ARTICLES]
        wrong_tags = [t for t in tags if t != raw["tag"]][:3]
        questions.append(
            QuizQuestion(
                question="이 기사의 주제로 가장 알맞은 분야는?",
                choices=[raw["tag"], *wrong_tags],
                answer=raw["tag"],
                explanation=f"이 기사는 {raw['tag']} 분야를 다루고 있어요.",
            )
        )
        quiz = QuizSet(questions=questions)
        self.last_quiz = quiz
        return quiz

    # ── 10~11단계: 채점 + 난이도 추천 (실제 grading.py 재사용) ─
    def grade(self, user_answers: list[str]) -> tuple[QuizResult, LevelRecommendation]:
        if self.last_quiz is None:
            raise RuntimeError("먼저 make_quiz() 로 퀴즈를 생성하세요.")
        result = grade_quiz(self.last_quiz, user_answers)
        recommendation = recommend_level(result.accuracy, self._profile["level"])
        return result, recommendation

    # ── 12~14단계: 난이도 조정 제안 ─────────────────────────────
    def propose_level_change(self, recommendation: LevelRecommendation) -> dict:
        if not recommendation.is_change():
            return {"reply": recommendation.message, "interrupt": None}
        self._pending_level_change = recommendation.suggested_level
        return {
            "reply": None,
            "interrupt": f"난이도를 '{recommendation.suggested_level}'(으)로 변경할까요? (목업 확인)",
        }

    # ── 내부 헬퍼 ────────────────────────────────────────────
    def _require_article(self) -> None:
        if self.current_article is None:
            raise RuntimeError("먼저 select_article() 로 기사를 선택하세요.")
