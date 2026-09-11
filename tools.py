"""
tools.py — Agent Tool 정의 (설계서 2.5)

  - news_search       : 학습 주제 관련 최신 영문 뉴스 검색 (API, Guardian Open Platform)
  - update_preference : 선호 주제 / 난이도 변경 (Custom, Store 쓰기 + HITL 보호)

강의 [4] Basic Agent "1. Tool 사용" 의 @tool 데코레이터 방식.
Store/Context 접근은 강의 [5] "4. Long-term Memory" 의 runtime 주입 패턴을 따른다.

[뉴스 소스 변경 메모]
  기존: NewsAPI.org — content 필드가 요금제와 무관하게 200자로 강제 절단되어
        (`...[+1234 chars]` 꼬리표까지 붙음) 기사 "전문"을 학습자료/퀴즈에 못 씀.
  변경: Guardian Open Platform (content.guardianapis.com) — show-fields=bodyText 로
        기사 본문 전체(순수 텍스트, HTML 제거)를 받아올 수 있어 교체함.
        무료 Developer 키 필요: https://bonobo.capi.gutools.co.uk/register/developer
        (비상업적 이용 한정. 정확한 rate limit 은 발급받은 키 대시보드에서 확인)

  API 키/URL 은 config.py 를 건드리지 않기 위해 이 파일 안에서 직접 os.getenv 로 읽는다
  (파일 소유권 규칙: config.py 는 박서윤 담당 — 팀 분업 문서 참고).
  timeout/재시도 횟수/페이지 크기/mock 여부는 provider-agnostic 값이라 기존처럼 config 에서 읽는다.
"""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone

import requests
from langchain.tools import tool, ToolRuntime

from . import config
from .memory import load_profile, save_profile

# ──────────────────────────────────────────────────────────────
# Guardian Open Platform 설정 (config.py 비침범 — 이 파일 안에서만 관리)
# ──────────────────────────────────────────────────────────────
_GUARDIAN_API_URL = "https://content.guardianapis.com/search"
_GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY", "")

# ──────────────────────────────────────────────────────────────
# 목(mock) 데이터 — NEWSLINGO_USE_MOCK_NEWS=true 일 때 사용 (발표/오프라인용)
#   Guardian /search 응답과 동일한 shape(webTitle/webUrl/fields.bodyText 등)으로 맞춰서,
#   목 모드에서도 실제 정규화 경로(_normalize)를 100% 동일하게 통과하게 한다.
#   (예전엔 NewsAPI shape 로 되어 있어 실제 API의 200자 절단 문제가 목 모드에선 안 보였음)
# ──────────────────────────────────────────────────────────────
_MOCK_ARTICLES: list[dict] = [
    {
        "id": "technology/2026/sep/08/ai-models-reasoning",
        "type": "article",
        "sectionId": "technology",
        "sectionName": "Technology",
        "webTitle": "AI models are getting better at reasoning, researchers say",
        "webUrl": "https://www.theguardian.com/technology/2026/sep/08/ai-models-reasoning",
        "webPublicationDate": "2026-09-08T09:00:00Z",
        "fields": {
            "trailText": "New benchmarks show large language models improving on multi-step logic tasks.",
            "bodyText": (
                "Researchers reported that recent large language models have been trained "
                "with new techniques that improve step-by-step reasoning. The breakthrough "
                "could help AI systems assist with scientific work, though experts caution "
                "that reliability still needs to be verified across domains. The team said "
                "the next round of testing would focus on real-world tasks rather than "
                "benchmark scores alone, since benchmark performance does not always "
                "translate into practical usefulness."
            ),
        },
    },
    {
        "id": "business/2026/sep/07/chipmakers-ai-processors",
        "type": "article",
        "sectionId": "business",
        "sectionName": "Business",
        "webTitle": "Chipmakers race to build faster processors for AI training",
        "webUrl": "https://www.theguardian.com/business/2026/sep/07/chipmakers-ai-processors",
        "webPublicationDate": "2026-09-07T12:30:00Z",
        "fields": {
            "trailText": "Semiconductor companies are investing heavily in next-generation hardware.",
            "bodyText": (
                "Several semiconductor firms have announced new processors designed for "
                "artificial intelligence workloads. Demand has been driven by companies "
                "that are expanding their data centers. Analysts expect prices to remain "
                "high as long as supply stays tight, and some manufacturers have already "
                "said their production lines are booked for the rest of the year."
            ),
        },
    },
    {
        "id": "education/2026/sep/06/language-apps-ai-tutors",
        "type": "article",
        "sectionId": "education",
        "sectionName": "Education",
        "webTitle": "Language learning apps adopt AI tutors",
        "webUrl": "https://www.theguardian.com/education/2026/sep/06/language-apps-ai-tutors",
        "webPublicationDate": "2026-09-06T08:15:00Z",
        "fields": {
            "trailText": "Education startups add conversational AI features for learners.",
            "bodyText": (
                "Language learning platforms are adding AI tutors that can hold a "
                "conversation with students. Teachers say the tools are helpful for "
                "practice, but they warn that learners should still check explanations "
                "against a textbook or a human teacher, since the tutors occasionally "
                "produce answers that sound confident but are incorrect."
            ),
        },
    },
    {
        "id": "world/2026/sep/05/governments-ai-transparency",
        "type": "article",
        "sectionId": "world",
        "sectionName": "World news",
        "webTitle": "Governments debate new rules for AI transparency",
        "webUrl": "https://www.theguardian.com/world/2026/sep/05/governments-ai-transparency",
        "webPublicationDate": "2026-09-05T16:45:00Z",
        "fields": {
            "trailText": "Lawmakers discuss disclosure requirements for AI-generated content.",
            "bodyText": (
                "Governments around the world have been debating rules that would require "
                "companies to label AI-generated content. Supporters argue that "
                "transparency protects the public, while critics say the rules may be hard "
                "to enforce across borders and could push some companies to relocate their "
                "AI operations to countries with lighter regulation."
            ),
        },
    },
    {
        "id": "science/2026/sep/04/ai-translation-manuscripts",
        "type": "article",
        "sectionId": "science",
        "sectionName": "Science",
        "webTitle": "Startup uses AI to translate old manuscripts",
        "webUrl": "https://www.theguardian.com/science/2026/sep/04/ai-translation-manuscripts",
        "webPublicationDate": "2026-09-04T10:00:00Z",
        "fields": {
            "trailText": "A research team applies machine translation to historical texts.",
            "bodyText": (
                "A startup has developed an AI system that helps historians translate old "
                "manuscripts. The model was trained on scanned documents. The team says the "
                "work has been slow but rewarding, and they hope the tool will eventually "
                "help libraries and museums make more of their archives searchable in "
                "modern languages."
            ),
        },
    },
    {
        "id": "environment/2026/sep/03/ai-weather-forecasts",
        "type": "article",
        "sectionId": "environment",
        "sectionName": "Environment",
        "webTitle": "AI-powered weather models improve local forecasts",
        "webUrl": "https://www.theguardian.com/environment/2026/sep/03/ai-weather-forecasts",
        "webPublicationDate": "2026-09-03T07:20:00Z",
        "fields": {
            "trailText": "Meteorologists test machine learning models for short-term prediction.",
            "bodyText": (
                "Weather agencies have started testing AI models that can produce local "
                "forecasts more quickly than traditional simulations. Early results have "
                "been promising, but forecasters still review every prediction before it "
                "is published, since the models can struggle with rare or extreme events "
                "that were underrepresented in their training data."
            ),
        },
    },
]


def _to_ymd(raw: str) -> str:
    """ISO 8601 문자열을 YYYY-MM-DD 로 변환 (실패 시 오늘 날짜)."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _clean_text(raw: str) -> str:
    """HTML 태그/엔티티 제거 + 공백 정리.

    Guardian 의 bodyText 는 보통 이미 순수 텍스트지만, trailText 등에는 <strong> 같은
    가벼운 마크업이 섞여 있을 수 있어 방어적으로 한 번 더 벗겨낸다.
    """
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize(article: dict) -> dict:
    """Guardian Content API 응답 항목(또는 동일 shape 의 mock)을 공통 형태로 정리.

    설계서 2.5 news_search 반환 형태: 제목/URL/요약/출처 + 학습자료 생성용 본문(content).
    """
    fields = article.get("fields") or {}
    body_text = _clean_text(fields.get("bodyText") or "")
    trail_text = _clean_text(fields.get("trailText") or "")
    section = article.get("sectionName")

    return {
        "title": _clean_text(article.get("webTitle", "")),
        "url": article.get("webUrl", ""),
        "summary": trail_text or body_text[:100],
        "source": f"The Guardian ({section})" if section else "The Guardian",
        "published_date": _to_ymd(article.get("webPublicationDate", "")),
        # 기사 "전문" — Guardian bodyText 는 NewsAPI content 와 달리 절단되지 않는다.
        "content": body_text or trail_text,
    }


def _fetch_from_guardian(query: str) -> list[dict]:
    """Guardian Content API /search 호출 (실패 시 예외를 그대로 던짐).

    show-fields=trailText,bodyText 로 요약(trailText)과 본문 전체(bodyText)를 함께 받는다.
    order-by=newest 로 최신순 정렬 (설계서 취지: 최신 뉴스로 학습).
    """
    resp = requests.get(
        _GUARDIAN_API_URL,
        params={
            "q": query,
            "api-key": _GUARDIAN_API_KEY,
            "order-by": "newest",
            "page-size": config.NEWS_RAW_PAGE_SIZE,
            "show-fields": "trailText,bodyText",
        },
        timeout=config.NEWS_SEARCH_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", {}).get("results", [])


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
            elif not _GUARDIAN_API_KEY:
                return json.dumps(
                    {
                        "error": (
                            "GUARDIAN_API_KEY 가 없습니다. .env 에 키를 설정하거나 "
                            "목 모드(NEWSLINGO_USE_MOCK_NEWS=true)를 사용하세요. "
                            "무료 키 발급: https://bonobo.capi.gutools.co.uk/register/developer"
                        ),
                        "articles": [],
                    },
                    ensure_ascii=False,
                )
            else:
                raw = _fetch_from_guardian(query)

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
