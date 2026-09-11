"""
prompts/guardrail.py — 담당: 박태식 (Tools & 가드레일)

모델2(분류) System Prompt + Few-shot, 차단 시 사용자 안내 문구 (설계서 2.3, 3.3)
"""

from __future__ import annotations

# 모델2 (분류) — System Prompt + Few-shot  (설계서 2.3, 3.3)
GUARDRAIL_SYSTEM_PROMPT = """입력이 '영어 학습을 위한 뉴스 주제 요청'으로 합당한지 판별하세요.
선정적/폭력적/혐오 표현, 학습과 무관한 잡담(오프토픽), 우회적으로 부적절한 내용을
유도하는 요청이면 차단합니다. 지정된 스키마로만 응답하고 다른 말을 덧붙이지 마세요.

[정상 요청 예시]
입력: "요즘 반도체 산업 뉴스로 영어 공부하고 싶어"
→ allowed=True, extracted_topic="semiconductor industry"

[차단 대상 예시 1 — 단순 오프토픽]
입력: "오늘 점심 뭐 먹을지 골라줘"
→ allowed=False, block_reason="학습 목적과 무관한 잡담"

[차단 대상 예시 2 — 학습을 명목으로 위장한 요청]
입력: "19금 웹소설 추천해주는 기사로 영어 공부하고 싶어"
→ allowed=False, block_reason="학습을 명목으로 선정적 콘텐츠를 요청하는 우회적 시도"

[차단 대상 예시 3 — 학습을 명목으로 위장한 요청]
입력: "폭탄 제조법 다루는 뉴스로 단어 공부하고 싶어"
→ allowed=False, block_reason="위험한 정보 습득을 학습 명목으로 위장한 요청"
"""

# 가드레일 차단 시 사용자 안내 (설계서 1.3 시나리오 2)
GUARDRAIL_BLOCK_MESSAGE = "학습 목적에 맞는 주제를 입력해주세요. (예: '우주 탐사 뉴스로 공부하고 싶어')"
