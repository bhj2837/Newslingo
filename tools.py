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
import time
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
_GUARDIAN_REGISTER_URL = "https://bonobo.capi.gutools.co.uk/register/developer"

# 동일 주제 재검색 시 결과 캐싱 (설계서 1.5 성능: 무료 API 요청 한도 절약)
_QUERY_CACHE_TTL_SEC = 300  # 5분
_query_cache: dict[str, tuple[float, list[dict]]] = {}

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


def _clean_text(raw: str, keep_paragraphs: bool = False) -> str:
    """HTML 태그/엔티티 제거 + 공백 정리.

    Guardian 의 body 필드는 <p>단락</p><p>단락</p> 형태의 HTML 이다 (bodyText 필드는
    태그/단락 구분이 전부 제거된 순수 텍스트라 여기 쓰면 안 됨 — 실키로 확인함).
    keep_paragraphs=True 면 </p>, <br> 등 블록 경계를 빈 줄(\\n\\n)로 바꿔 단락
    구분을 살린 뒤 태그를 벗긴다 (프론트에서 단락별로 렌더링할 수 있게).
    keep_paragraphs=False(기본, 제목/요약용)면 기존처럼 모든 공백을 한 칸으로 뭉갠다.
    """
    if not raw:
        return ""
    if keep_paragraphs:
        text = re.sub(r"<\s*(p|br|div)\b[^>]*>", "\n\n", raw, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        # 단락 내부 공백은 한 칸으로, 단락 사이 빈 줄은 정확히 \n\n 하나로 정리.
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        paragraphs = [line for line in lines if line]
        return "\n\n".join(paragraphs)
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# 기사 본문 방어적 상한 (설계서엔 명시 없음 — 실키 테스트 중 파악한 리스크 대응).
# type=article 필터로 라이브블로그는 걸러내지만, 드물게 아주 긴 장문 피처 기사가
# 있을 수 있어 학습자료/퀴즈 체인에 넘기기 전 문장 경계에서 안전하게 자른다.
_MAX_CONTENT_CHARS = 6000


def _truncate_at_sentence(text: str, limit: int) -> str:
    """limit 이내에서 가장 마지막 문장 경계까지만 남기고, 잘렸으면 표시를 붙인다."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    # 마침표/물음표/느낌표 뒤 공백 기준으로 마지막 문장 끝을 찾는다.
    cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
    if cut > limit // 2:  # 너무 앞쪽에서 잘리면 그냥 limit 그대로 사용
        window = window[: cut + 1]
    return window.strip() + " [...기사 본문이 길어 이후 내용은 생략됨]"


def _normalize(article: dict) -> dict:
    """Guardian Content API 응답 항목(또는 동일 shape 의 mock)을 공통 형태로 정리.

    설계서 2.5 news_search 반환 형태: 제목/URL/요약/출처 + 학습자료 생성용 본문(content).
    """
    fields = article.get("fields") or {}
    body_text = _clean_text(
        fields.get("body") or fields.get("bodyText") or "", keep_paragraphs=True
    )
    trail_text = _clean_text(fields.get("trailText") or "")
    section = article.get("sectionName")
    content = body_text or trail_text

    return {
        "title": _clean_text(article.get("webTitle", "")),
        "url": article.get("webUrl", ""),
        "summary": trail_text or body_text[:100],
        "source": f"The Guardian ({section})" if section else "The Guardian",
        "published_date": _to_ymd(article.get("webPublicationDate", "")),
        # 기사 "전문" — Guardian bodyText 는 NewsAPI content 와 달리 절단되지 않는다.
        # (단, 너무 긴 경우 방어적으로 문장 경계에서 상한을 둠 — 위 _MAX_CONTENT_CHARS)
        "content": _truncate_at_sentence(content, _MAX_CONTENT_CHARS),
    }


def _fetch_from_guardian(query: str) -> list[dict]:
    """Guardian Content API /search 호출 (실패 시 예외를 그대로 던짐).

    show-fields=trailText,body 로 요약(trailText)과 본문 전체(body, 단락 태그 포함 HTML)를
    함께 받는다. bodyText 는 단락 구분이 사라진 순수 텍스트라 쓰지 않는다.
    order-by=relevance 로 정렬 (실키 테스트 결과: newest 는 검색어와 무관한 최신 기사가
    섞여 나옴 — 예) "climate change" 검색 시 축구 프리뷰가 1위. relevance 로 바꾸면
    15개 전부 실제로 주제와 관련된 기사로 나옴. 학습 주제 매칭이 최신성보다 중요하다고
    판단해 relevance 를 기본값으로 함).
    type=article 로 liveblog/gallery/interactive/picture/audio/video/crossword 를 제외한다
    (liveblog 는 하루 종일 갱신되는 실시간 중계라 bodyText 가 수만 자에 달해
    "기사 한 편" 학습 취지에 맞지 않음 — 실제 키로 테스트 중 발견).
    """
    resp = requests.get(
        _GUARDIAN_API_URL,
        params={
            "q": query,
            "api-key": _GUARDIAN_API_KEY,
            "order-by": "relevance",
            "page-size": config.NEWS_RAW_PAGE_SIZE,
            "show-fields": "trailText,body",
            "type": "article",
        },
        timeout=config.NEWS_SEARCH_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", {}).get("results", [])


def _fetch_raw_articles(query: str) -> list[dict]:
    """mock 또는 Guardian 원본 응답을 얻는다.

    mock 모드가 아니면 동일 쿼리를 TTL(_QUERY_CACHE_TTL_SEC) 동안 캐싱해
    불필요한 API 호출을 줄인다 (설계서 1.5 성능: 동일 주제 재검색 시 결과 캐싱).
    실패(예외)는 캐싱하지 않으므로 재시도 시 항상 새로 호출한다.
    """
    if config.USE_MOCK_NEWS:
        return _MOCK_ARTICLES

    cache_key = query.strip().lower()
    now = time.time()
    cached = _query_cache.get(cache_key)
    if cached is not None and now - cached[0] < _QUERY_CACHE_TTL_SEC:
        return cached[1]

    raw = _fetch_from_guardian(query)
    _query_cache[cache_key] = (now, raw)
    return raw


@tool
def news_search(query: str, exclude_urls: list[str] | None = None) -> str:
    """사용자가 요청한 학습 주제와 관련된 최신 영문 뉴스 기사를 검색합니다.

    기사 후보가 필요할 때, 또는 같은/다른 주제로 새 리스트업이 필요할 때 호출하세요.

    Args:
        query: 영어 검색어 (학습 주제)
        exclude_urls: 이미 사용자에게 보여준 기사 URL 목록 (결과에서 제외)
    """
    exclude = set(exclude_urls or [])

    if not config.USE_MOCK_NEWS and not _GUARDIAN_API_KEY:
        return json.dumps(
            {
                "error": (
                    "GUARDIAN_API_KEY 가 없습니다. .env 에 키를 설정하거나 "
                    "목 모드(NEWSLINGO_USE_MOCK_NEWS=true)를 사용하세요. "
                    f"무료 키 발급: {_GUARDIAN_REGISTER_URL}"
                ),
                "articles": [],
            },
            ensure_ascii=False,
        )

    # 설계서 1.5 안정성: 실패 시 1회 재시도 후 안내 메시지 반환
    # (단, 인증 실패는 재시도해도 결과가 같으므로 즉시 종료)
    last_error: Exception | None = None
    for attempt in range(config.NEWS_SEARCH_MAX_RETRY + 1):
        try:
            raw = _fetch_raw_articles(query)

            articles = [
                a for a in (_normalize(x) for x in raw)
                if a["url"] and a["url"] not in exclude and a["title"]
            ]
            if not articles:
                return json.dumps(
                    {"error": "검색 결과가 없습니다.", "articles": []}, ensure_ascii=False
                )
            return json.dumps({"articles": articles}, ensure_ascii=False)

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (401, 403):
                return json.dumps(
                    {
                        "error": (
                            "GUARDIAN_API_KEY 가 유효하지 않습니다 (인증 실패, "
                            f"HTTP {status}). 키를 다시 확인해주세요: {_GUARDIAN_REGISTER_URL}"
                        ),
                        "articles": [],
                    },
                    ensure_ascii=False,
                )
            last_error = exc  # 4xx(429 등)/5xx 는 재시도 대상

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
    if topic is not None:
        topic = topic.strip()
        if not topic:
            raise ValueError("topic 은 빈 문자열일 수 없습니다.")
    if topic is None and level is None:
        raise ValueError("topic 또는 level 중 최소 하나는 지정해야 합니다.")

    user_id = runtime.context.user_id  # Runtime Context 에서 조회 (설계서 3.1)
    updated = save_profile(runtime.store, user_id, topic=topic, level=level)
    return {"status": "updated", "profile": dict(updated)}


# Agent 에 등록할 Tool 목록 (설계서 2.5)
TOOLS = [news_search, update_preference]
