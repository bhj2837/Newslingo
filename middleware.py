"""
middleware.py — Agent 미들웨어 (설계서 3.2)

┌ 이름 ───────────────────────┬ Hook ───────────┬ Built-in/Custom ┐
│ ProfileInjectionMiddleware   │ wrap_model_call │ Custom          │  Store 프로필 → System Prompt 주입
│ HumanInTheLoopMiddleware     │ wrap_tool_call  │ Built-in        │  update_preference 승인(2차 재확인)
│ SummarizationMiddleware      │ before_model    │ Built-in        │  대화 이력 자동 요약
│ ModelFallbackMiddleware      │ wrap_model_call │ Built-in        │  모델1 실패 시 대체 모델
└─────────────────────────────┴─────────────────┴─────────────────┘

강의 [5] Advanced Agent "1. Runtime & State", "2. Middleware" 의 패턴을 따른다.
"""

from __future__ import annotations

from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelFallbackMiddleware,
    SummarizationMiddleware,
    dynamic_prompt,
)

from . import config
from .memory import load_profile
from .prompts import MAIN_SYSTEM_PROMPT


# ──────────────────────────────────────────────────────────────
# Custom : Store 의 선호 주제/난이도를 System Prompt 에 주입
#   (강의 [5] "1-1. System Message 동적 정의" 의 wrap_model_call → dynamic_prompt 축약형)
# ──────────────────────────────────────────────────────────────
@dynamic_prompt
def profile_injection(request) -> str:
    """매 모델 호출 직전, 현재 사용자 프로필 + 현재 기사/학습자료를 시스템 프롬프트에 덧붙인다.

    설계서 3.2: Store 조회 실패 시 기본값(중급, 무관)으로 폴백.

    2-a 수정: 기존엔 프로필(topic/level)만 주입해서 채팅 Agent 가 사용자가 방금
    고른 기사의 원문/번역/전문용어/문법을 전혀 몰랐다 (그래서 엉뚱한 문장을
    지어내 답함). Context.article_* 필드(service.py 가 chat() 호출마다 채워서
    넘김)를 읽어 있으면 같이 붙인다 — 기사 선택 전이라 비어있으면 이 블록은 생략.
    """
    try:
        user_id = request.runtime.context.user_id
        profile = load_profile(request.runtime.store, user_id)
        topic = profile["topic"] or "(아직 없음)"
        level = profile["level"]
    except Exception:  # noqa: BLE001 - 설계서 요구: 조회 실패 시 폴백
        topic, level = "(아직 없음)", config.DEFAULT_LEVEL

    prompt = (
        f"{MAIN_SYSTEM_PROMPT}\n\n"
        f"[현재 사용자 프로필]\n- 선호 주제: {topic}\n- 현재 난이도: {level}"
    )

    article_title = getattr(request.runtime.context, "article_title", "") or ""
    article_text = getattr(request.runtime.context, "article_text", "") or ""
    material_summary = getattr(request.runtime.context, "study_material_summary", "") or ""

    if article_text:
        prompt += (
            f"\n\n[현재 학습 중인 기사]\n제목: {article_title}\n\n원문:\n{article_text}"
        )
        if material_summary:
            prompt += f"\n\n[이 기사의 학습자료 — 번역/용어/문법]\n{material_summary}"
        prompt += (
            "\n\n위 원문/학습자료를 기반으로 영어공부를 할 수 있도록"
        )

    return prompt


# ──────────────────────────────────────────────────────────────
# Built-in 미들웨어 팩토리
# ──────────────────────────────────────────────────────────────
def human_in_the_loop() -> HumanInTheLoopMiddleware:
    """update_preference(Store 쓰기) 호출 전 사람의 승인을 받는다 (설계서 3.3).

    UI/CLI 에서 버튼 클릭 = '1차 의사표시', 여기서 걸리는 interrupt = '2차 재확인'.
    거부/무응답이면 Tool 이 실행되지 않아 기존 Store 값이 유지된다.
    """
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "update_preference": {
                "allowed_decisions": ["approve", "edit", "reject"],
            },
        },
        description_prefix="선호/난이도 변경은 되돌릴 수 없어요. 진행할까요?",
    )


def summarization() -> SummarizationMiddleware:
    """대화 이력이 길어지면 자동 요약해 토큰 소비를 줄인다 (설계서 1.5 성능)."""
    return SummarizationMiddleware(
        model=config.SUMMARY_MODEL,
        trigger=("messages", 12),
        keep=("messages", 4),
    )


def model_fallback() -> ModelFallbackMiddleware:
    """모델1 호출이 예외를 던지면 대체 모델로 자동 전환 (설계서 3.2)."""
    return ModelFallbackMiddleware(config.FALLBACK_MODEL)


def build_middleware() -> list:
    """create_agent(middleware=...) 에 넣을 미들웨어 목록을 조립한다.

    순서: 프롬프트 주입 → 요약 → 모델 폴백 → HITL
    """
    return [
        profile_injection,
        summarization(),
        model_fallback(),
        human_in_the_loop(),
    ]
