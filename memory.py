"""
memory.py — 단기/장기 메모리 (설계서 3.1 Context)

  - 단기 메모리 : checkpointer + thread_id      → 세션 내 채팅 맥락 유지 (강의 [4] 2. 단기Memory)
  - 장기 메모리 : Store (namespace = user_id)   → 선호 주제/난이도 세션 간 유지 (강의 [5] 4. Long-term Memory)

강의에서는 InMemoryStore + managed_keys 로 관리했지만, 여기서는 동일 개념을
namespace/key 를 직접 지원하는 langgraph Store 로 더 깔끔하게 구현한다.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from . import config


class Profile(TypedDict):
    """장기 메모리에 저장되는 사용자 프로필 (설계서 3.1 profile)."""

    topic: str  # 선호 주제
    level: str  # 현재 난이도 (config.LEVELS 중 하나)


# 프로세스 내에서 공유되는 단일 인스턴스 (UI/CLI/노트북이 모두 같은 메모리를 본다)
_CHECKPOINTER = InMemorySaver()
_STORE = InMemoryStore()

# 장기 메모리 안에서 프로필을 찾는 key (namespace 는 사용자별로 나뉨)
_PROFILE_KEY = "profile"


def get_checkpointer() -> InMemorySaver:
    """단기 메모리 저장소. create_agent(checkpointer=...) 로 연결한다."""
    return _CHECKPOINTER


def get_store() -> InMemoryStore:
    """장기 메모리 저장소. create_agent(store=...) 로 연결한다."""
    return _STORE


def _namespace(user_id: str) -> tuple[str, str]:
    """사용자별 장기 메모리 네임스페이스 (설계서 3.1: Store 네임스페이스 구분)."""
    return (user_id, config.APP_NAME)


def load_profile(store: BaseStore, user_id: str) -> Profile:
    """장기 메모리에서 프로필을 읽는다. 없으면 기본값(중급/주제없음)으로 폴백."""
    item = store.get(_namespace(user_id), _PROFILE_KEY)
    if item is None:
        return Profile(topic=config.DEFAULT_TOPIC, level=config.DEFAULT_LEVEL)
    value = item.value
    return Profile(
        topic=value.get("topic", config.DEFAULT_TOPIC),
        level=value.get("level", config.DEFAULT_LEVEL),
    )


def save_profile(
    store: BaseStore,
    user_id: str,
    *,
    topic: str | None = None,
    level: str | None = None,
) -> Profile:
    """프로필을 부분 갱신한다. (update_preference Tool / 온보딩에서 호출)

    level 값 검증은 호출부(tools.update_preference)에서 이미 끝났다고 가정한다.
    """
    current = load_profile(store, user_id)
    updated = Profile(
        topic=topic if topic is not None else current["topic"],
        level=level if level is not None else current["level"],
    )
    store.put(_namespace(user_id), _PROFILE_KEY, dict(updated))
    return updated
