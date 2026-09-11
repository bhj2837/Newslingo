"""
tools.py — Agent Tool 정의 (설계서 2.5)

  - news_search       : 학습 주제 관련 최신 영문 뉴스 검색 (API, NewsAPI.org)
  - update_preference : 선호 주제 / 난이도 변경 (Custom, Store 쓰기 + HITL 보호)

강의 [4] Basic Agent "1. Tool 사용" 의 @tool 데코레이터 방식.
Store/Context 접근은 강의 [5] "4. Long-term Memory" 의 runtime 주입 패턴을 따른다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import requests
from langchain.tools import tool, ToolRuntime

from . import config
from .memory import load_profile, save_profile

# ──────────────────────────────────────────────────────────────
# 목(mock) 데이터 — NEWSLINGO_USE_MOCK_NEWS=true 일 때 사용 (발표/오프라인용)
# ──────────────────────────────────────────────────────────────
_MOCK_ARTICLES: list[dict] = [
    {
        "title": "AI models are getting better at reasoning, researchers say",
        "url": "https://example.com/news/ai-reasoning",
        "description": "New benchmarks show large language models improving on multi-step logic tasks.",
        "source": "Example Tech Daily",
        "publishedAt": "2026-09-08T09:00:00Z",
        "content": (
            "Researchers reported that recent large language models have been trained "
            "with new techniques that improve step-by-step reasoning. The breakthrough "
            "could help AI systems assist with scientific work, though experts caution "
            "that reliability still needs to be verified across domains."
        ),
    },
    {
        "title": "Chipmakers race to build faster processors for AI training",
        "url": "https://example.com/news/chips-ai",
        "description": "Semiconductor companies are investing heavily in next-generation hardware.",
        "source": "Global Business Wire",
        "publishedAt": "2026-09-07T12:30:00Z",
        "content": (
            "Several semiconductor firms have announced new processors designed for "
            "artificial intelligence workloads. Demand has been driven by companies "
            "that are expanding their data centers. Analysts expect prices to remain high."
        ),
    },
    {
        "title": "Language learning apps adopt AI tutors",
        "url": "https://example.com/news/language-ai-tutor",
        "description": "Education startups add conversational AI features for learners.",
        "source": "EdTech Report",
        "publishedAt": "2026-09-06T08:15:00Z",
        "content": (
            "Language learning platforms are adding AI tutors that can hold a "
            "conversation with students. Teachers say the tools are helpful for "
            "practice, but they warn that learners should still check explanations."
        ),
    },
    {
        "title": "Governments debate new rules for AI transparency",
        "url": "https://example.com/news/ai-policy",
        "description": "Lawmakers discuss disclosure requirements for AI-generated content.",
        "source": "Policy Journal",
        "publishedAt": "2026-09-05T16:45:00Z",
        "content": (
            "Governments around the world have been debating rules that would require "
            "companies to label AI-generated content. Supporters argue that "
            "transparency protects the public, while critics say the rules may be hard "
            "to enforce."
        ),
    },
    {
        "title": "Startup uses AI to translate old manuscripts",
        "url": "https://example.com/news/ai-translation-manuscripts",
        "description": "A research team applies machine translation to historical texts.",
        "source": "Science Now",
        "publishedAt": "2026-09-04T10:00:00Z",
        "content": (
            "A startup has developed an AI system that helps historians translate old "
            "manuscripts. The model was trained on scanned documents. The team says the "
            "work has been slow but rewarding."
        ),
    },
    {
        "title": "AI-powered weather models improve local forecasts",
        "url": "https://example.com/news/ai-weather",
        "description": "Meteorologists test machine learning models for short-term prediction.",
        "source": "Earth Observer",
        "publishedAt": "2026-09-03T07:20:00Z",
        "content": (
            "Weather agencies have started testing AI models that can produce local "
            "forecasts more quickly than traditional simulations. Early results have "
            "been promising, but forecasters still review every prediction."
        ),
    },
]


def _to_ymd(raw: str) -> str:
    """ISO 8601 문자열을 YYYY-MM-DD 로 변환 (실패 시 오늘 날짜)."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _normalize(article: dict) -> dict:
    """NewsAPI / mock 응답을 공통 형태로 정리."""
    src = article.get("source")
    source_name = src.get("name") if isinstance(src, dict) else (src or "Unknown")
    return {
        "title": article.get("title", "").strip(),
        "url": article.get("url", ""),
        "summary": (article.get("description") or "").strip(),
        "source": source_name,
        "published_date": _to_ymd(article.get("publishedAt", "")),
        "content": (article.get("content") or article.get("description") or "").strip(),
    }


def _fetch_from_newsapi(query: str) -> list[dict]:
    """NewsAPI.org /v2/everything 호출 (실패 시 예외를 그대로 던짐)."""
    resp = requests.get(
        config.NEWS_API_URL,
        params={
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": config.NEWS_RAW_PAGE_SIZE,
        },
        headers={"X-Api-Key": config.NEWS_API_KEY},
        timeout=config.NEWS_SEARCH_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("articles", [])


@tool
def news_search(query: str, exclude_urls: list[str] | None = None) -> str:
    """사용자가 요청한 학습 주제와 관련된 최신 영문 뉴스 기사를 검색합니다.

    기사 후보가 필요할 때, 또는 같은/다른 주제로 새 리스트업이 필요할 때 호출하세요.

    Args:
        query: 영어 검색어 (학습 주제)
        exclude_urls: 이미 사용자에게 보여준 기사 URL 목록 (결과에서 제외)
    """
    exclude = set(exclude_urls or [])

    # 설계서 1.5 안정성: 실패 시 1회 재시도 후 안내 메시지 반환
    last_error: Exception | None = None
    for attempt in range(config.NEWS_SEARCH_MAX_RETRY + 1):
        try:
            if config.USE_MOCK_NEWS:
                raw = _MOCK_ARTICLES
            elif not config.NEWS_API_KEY:
                return json.dumps(
                    {"error": "NEWS_API_KEY 가 없습니다. .env 설정 또는 목 모드를 사용하세요.",
                     "articles": []},
                    ensure_ascii=False,
                )
            else:
                raw = _fetch_from_newsapi(query)

            articles = [
                a for a in (_normalize(x) for x in raw)
                if a["url"] and a["url"] not in exclude and a["title"]
            ]
            if not articles:
                return json.dumps(
                    {"error": "검색 결과가 없습니다.", "articles": []}, ensure_ascii=False
                )
            return json.dumps({"articles": articles}, ensure_ascii=False)

        except Exception as exc:  # noqa: BLE001 - 재시도 목적
            last_error = exc

    return json.dumps(
        {
            "error": f"일시적으로 기사를 가져올 수 없어요. ({type(last_error).__name__})",
            "articles": [],
        },
        ensure_ascii=False,
    )


@tool
def update_preference(
    runtime: ToolRuntime,
    topic: str | None = None,
    level: str | None = None,
) -> dict:
    """사용자의 선호 주제 또는 현재 난이도를 변경합니다.

    사용자가 명시적으로 변경을 요청했거나, 퀴즈 후 난이도 조정에 동의했을 때만 호출하세요.
    이 Tool 은 Human-in-the-loop 미들웨어로 보호되어, 승인 후에만 실제로 실행됩니다.

    Args:
        topic: 새 선호 주제 (선택)
        level: 새 난이도 — 초급 / 중급 / 고급 중 하나 (선택)
    """
    if level is not None and level not in config.LEVELS:
        # 설계서 2.5: 값 유효성 검증 실패 시 예외 발생, Store 변경 안 함
        raise ValueError(f"level 은 {config.LEVELS} 중 하나여야 합니다. (받은 값: {level!r})")
    if topic is None and level is None:
        raise ValueError("topic 또는 level 중 최소 하나는 지정해야 합니다.")

    user_id = runtime.context.user_id  # Runtime Context 에서 조회 (설계서 3.1)
    updated = save_profile(runtime.store, user_id, topic=topic, level=level)
    return {"status": "updated", "profile": dict(updated)}


# Agent 에 등록할 Tool 목록 (설계서 2.5)
TOOLS = [news_search, update_preference]
