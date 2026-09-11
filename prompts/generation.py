"""
prompts/generation.py — 담당: 이지영 (Structured Output & 로직)

기사추천 / 학습자료 / 퀴즈 생성 LCEL 체인의 프롬프트 템플릿 (설계서 2.4)
※ 중괄호 변수명({topic} 등)은 chains.py 의 invoke 입력 키와 반드시 일치해야 함.
"""

from __future__ import annotations

# 기사 추천 : news_search 원본 결과를 난이도에 맞춰 5개로 정리 (설계서 2.2 4단계)
ARTICLE_RECOMMENDER_TEMPLATE = """당신은 영어 학습용 뉴스 큐레이터입니다.
아래 '검색된 기사 목록' 중에서 학습 주제와 사용자 난이도에 가장 적합한 기사 5개를 골라
ArticleCandidateList 스키마로 정리하세요.

- 학습 주제: {topic}
- 사용자 난이도: {level}
- 이미 사용자가 본 기사 URL (제외 대상): {seen_urls}

[검색된 기사 목록(JSON)]
{raw_articles}

규칙:
- 정확히 5개를 선택합니다. (목록이 5개 미만이면 있는 만큼 채우되 최대한 5개에 맞춥니다)
- 제외 대상 URL 은 고르지 않습니다.
- summary 는 한글 한 줄(100자 이내), keywords 는 2~5개.
- published_date 는 YYYY-MM-DD 형식으로 변환합니다.
"""

# 학습자료 생성 : 번역 / 전문용어 / 기본단어 / 문법 (설계서 2.2 6단계)
STUDY_MATERIAL_TEMPLATE = """당신은 영어 튜터입니다. 아래 기사로 학습자료를 만드세요.
사용자 난이도({level})에 맞춰 단어 난이도와 설명 깊이를 조절합니다.

[기사 제목]
{article_title}

[기사 본문]
{article_text}

ArticleStudyMaterial 스키마에 맞춰:
- translated_text: 자연스러운 한글 번역
- key_terms: 이 기사에서만 나오는 전문 용어 3~7개
- basic_vocab: 난이도에 맞는 기본 핵심 단어 3~7개
- grammar_points: 학습 가치가 높은 문법 포인트 1~3개
"""

# 퀴즈 생성 : 기사 + 채팅 로그 근거 (설계서 2.2 9단계, 테스트 TS-07)
QUIZ_TEMPLATE = """아래 기사와 학습 중 나눈 대화를 근거로 영어 학습 퀴즈 5문항을 만드세요.
난이도: {level}

[기사 본문]
{article_text}

[학습 중 대화 로그]
{chat_log}

규칙(QuizSet 스키마):
- 정확히 5문항, 각 문항 choices 는 4개.
- answer 는 choices 중 하나와 문자열이 정확히 일치.
- 기사/대화에 실제로 등장한 내용만 출제. 어휘·내용이해·문법을 골고루 섞습니다.
- question 과 explanation 은 한글로 작성합니다.
"""
