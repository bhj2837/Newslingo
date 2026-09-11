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
STUDY_MATERIAL_TEMPLATE = """당신은 **한국인에게 영어를 가르치는** 튜터입니다.
아래 영문 기사로 학습자료를 만드세요. 사용자 난이도({level})에 맞춰 단어 선택과 설명 깊이를 조절합니다.

[기사 제목]
{article_title}

[기사 본문]
{article_text}

가장 중요한 규칙 — **학습 대상은 영어입니다.**
- term / pattern / example 은 **반드시 영어**로 씁니다. 한국어 단어나 한국어 문법(조사·어미)을
  학습 항목으로 뽑으면 안 됩니다.
- meaning / explanation 만 한국어로 씁니다.
- example 은 **기사 본문에 실제로 있는 영어 문장을 그대로 발췌**합니다. 지어내지 마세요.

ArticleStudyMaterial 스키마에 맞춰:
- original_text   : 위 [기사 본문]을 요약하거나 생략하지 말고 **영어 원문 그대로 전부** 옮길 것
- translated_text : 기사 전문의 자연스러운 한글 번역 (일부만 번역하지 말고 전문을 번역할 것)
- key_terms       : 기사 주제 분야의 **전문 용어 영어 단어** (이 분야를 모르면 뜻이 안 잡히는 것)
- basic_vocab     : 전문 용어가 아닌 **일반 영어 빈출 단어**. key_terms 와 겹치지 않게
- grammar_points  : 기사 문장에서 뽑은 **영어 문법** 패턴

[좋은 예]
  key_terms   : term="threat intelligence" / meaning="위협 정보"
                example="according to a threat intelligence report the company published"
  basic_vocab : term="attempt" / meaning="시도하다"
                example="have attempted to use Anthropic's powerful models"
  grammar     : pattern="have + p.p. (현재완료)" / explanation="과거에 시작돼 현재까지 이어지는 일"
                example="Criminals ... have attempted to use"

[나쁜 예 — 절대 이렇게 하지 마세요]
  term="생물학적 오용"  (한국어 단어)
  pattern="~고 있다"    (한국어 문법)
  example="과학자는 연구를 한다"  (기사에 없는 한국어 예문)

기사가 길면 key_terms 와 basic_vocab 을 최소 개수(3개)에서 멈추지 말고 5~7개까지 채우세요.
"""

# 퀴즈 생성 : 기사 + 채팅 로그 근거 (설계서 2.2 9단계, 테스트 TS-07)
QUIZ_TEMPLATE = """아래 기사와 학습 중 나눈 대화를 근거로 영어 학습 퀴즈 5문항을 만드세요.
난이도: {level}

[기사 본문]
{article_text}

[학습 중 대화 로그]
{chat_log}

규칙(QuizSet 스키마):
- 정확히 5문항, 각 문항 choices 는 4개. answer 는 choices 중 하나와 문자열이 정확히 일치.
- **영어 실력을 묻는 문항으로 만드세요.** 기사 줄거리를 기억하는지 묻는 상식 퀴즈가 아닙니다.
- 문항 구성: **어휘 2문항 + 문법 1문항 + 문맥상 의미 파악 1문항 + 내용 이해 1문항.**
- 어휘·문법 문항은 **기사에 나온 영어 표현을 원문 그대로 인용**해서 출제합니다.
- 오답 3개는 정답과 **같은 품사·비슷한 길이·그럴듯한 뜻**으로 만들어 한눈에 티나지 않게 합니다.
- question 의 지시문과 explanation 은 한국어로 쓰되, **영어 표현은 원문 그대로** 인용합니다.
- explanation 에는 정답 근거와 함께 **오답이 왜 틀렸는지**도 적습니다.

[좋은 문항 예]
  question : 기사의 "Criminals ... have attempted to use" 에서 attempt 의 뜻으로 알맞은 것은?
  choices  : ["시도하다", "포기하다", "완료하다", "거부하다"]
"""
