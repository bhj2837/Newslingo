"""
뉴스링고 (Newslingo) — 뉴스 기사 기반 개인화 영어 학습 Agent

설계서: 6반 5조 AI Agent 설계서 (LangChain 1.x / create_agent)

주요 진입점
    from newslingo.service import LearningSession
    session = LearningSession(user_id="user_001")
"""

from .service import LearningSession

__all__ = ["LearningSession"]
__version__ = "0.1.0"
