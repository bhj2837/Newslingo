"""
config.py — 환경변수 로드 & 전역 상수

설계서 매핑
  - 2.3 LLM 모델 설계 : 모델1(메인) / 모델2(분류) 이름·파라미터
  - 1.5 제약 및 고려 사항 : 무료 뉴스 API 1개, 기본 난이도 = 중급
  - 2.2 동작 흐름 10~11단계 : 정답률 기반 난이도 조정 임계치
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# .env 파일을 환경변수로 로드 (강의 [3] LangChain 노트북과 동일한 방식)
load_dotenv(Path(__file__).with_name(".env"), override=True)


# ──────────────────────────────────────────────────────────────
# 1. 모델 설정 (설계서 2.3)
# ──────────────────────────────────────────────────────────────
# 모델1 : 메인 대화/생성 모델 - 기사 추천, 학습자료 생성, 채팅, 퀴즈 생성
MAIN_MODEL = "gpt-4o-mini"
MAIN_TEMPERATURE = 0.4

# 모델1 실패 시 대체 모델 (ModelFallbackMiddleware, 설계서 3.2)
FALLBACK_MODEL = "gpt-4o"

# 모델2 : 입력 가드레일 전용 분류 모델 - 판별 일관성을 위해 저온도로 별도 호출
CLASSIFIER_MODEL = "gpt-4o-mini"
CLASSIFIER_TEMPERATURE = 0.0

# 요약 미들웨어가 쓰는 모델 (설계서 3.2 SummarizationMiddleware)
SUMMARY_MODEL = "gpt-4o-mini"


# ──────────────────────────────────────────────────────────────
# 2. 난이도 / 프로필 기본값 (설계서 1.1, 1.5, 3.1)
# ──────────────────────────────────────────────────────────────
LEVELS: tuple[str, ...] = ("초급", "중급", "고급")
DEFAULT_LEVEL = "중급"
DEFAULT_TOPIC = ""  # 온보딩 전에는 선호 주제 없음

# Store 장기 메모리 네임스페이스 접두 (설계서 3.1 profile)
APP_NAME = "newslingo"


# ──────────────────────────────────────────────────────────────
# 3. 정답률 기반 난이도 추천 임계치 (설계서 2.2 11단계, 테스트 TS-08)
# ──────────────────────────────────────────────────────────────
LEVEL_UP_THRESHOLD = 0.8    # 정답률 80% 이상 → 상향 추천
LEVEL_DOWN_THRESHOLD = 0.4  # 정답률 40% 이하 → 하향 추천


# ──────────────────────────────────────────────────────────────
# 4. 뉴스 API 설정 (설계서 2.5 news_search, 1.5 안정성)
# ──────────────────────────────────────────────────────────────
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_URL = "https://newsapi.org/v2/everything"
NEWS_SEARCH_TIMEOUT = 10          # 초
NEWS_SEARCH_MAX_RETRY = 1         # 실패 시 1회 재시도
NEWS_RAW_PAGE_SIZE = 15           # LLM에 넘길 원본 기사 후보 개수

# 뉴스 API 키 없이도 데모가 돌아가도록 하는 목 모드
USE_MOCK_NEWS = os.getenv("NEWSLINGO_USE_MOCK_NEWS", "false").lower() == "true"


# ──────────────────────────────────────────────────────────────
# 5. Agent 실행 제약 (설계서 1.5 안정성)
# ──────────────────────────────────────────────────────────────
TOOL_CALL_LIMIT = 3  # Tool 호출 최대 횟수 (무한루프 방지)


def require_openai_key() -> None:
    """OpenAI 키가 없으면 친절한 에러를 던진다 (실행 초반에 호출)."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY 가 설정되지 않았습니다. "
            "newslingo/.env.example 을 참고해 .env 파일을 만들어주세요."
        )
