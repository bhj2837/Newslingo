"""
agent.py — 메인 대화 Agent 조립 (설계서 2.1 전체 구조도)

강의 [4] Basic Agent "create_agent(model, tools, ...)" +
강의 [5] Advanced Agent "middleware / checkpointer / store / context_schema" 조합.

이 Agent 의 책임 : 자유 채팅 학습 지원(설계서 2.2 7단계) & Tool 호출
  - news_search        : 채팅 중 "다른 주제/다른 리스트업" 요청 시
  - update_preference  : 채팅 중 선호 변경 요청 시 (HITL 보호)

기사 추천 / 학습자료 / 퀴즈 '생성'은 결정적 품질을 위해 agent 가 아니라
chains.py 의 LCEL 체인이 담당한다. (설계서 2.2 의 "LCEL 체인 호출" 단계들)
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain.agents import create_agent

from . import config
from .memory import get_checkpointer, get_store
from .middleware import build_middleware
from .models import get_main_model
from .tools import TOOLS


@dataclass
class Context:
    """Runtime Context (설계서 3.1) — 앱 호출 시 1회 전달, 세션 내 불변."""

    user_id: str


def build_agent():
    """뉴스링고 메인 Agent 를 생성한다.

    - model        : 모델1 (gpt-4o-mini)
    - tools        : news_search, update_preference
    - middleware   : 프로필 주입 / 요약 / 모델 폴백 / HITL
    - checkpointer : 단기 메모리 (thread_id 로 세션 구분)
    - store        : 장기 메모리 (user_id 네임스페이스)
    - context_schema : Context(user_id)
    """
    config.require_openai_key()

    return create_agent(
        model=get_main_model(),
        tools=TOOLS,
        system_prompt=None,  # 실제 시스템 프롬프트는 profile_injection 미들웨어가 동적 생성
        middleware=build_middleware(),
        checkpointer=get_checkpointer(),
        store=get_store(),
        context_schema=Context,
    )
