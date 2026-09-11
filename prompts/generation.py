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
QUIZ_TEMPLATE = """Create an English-learning quiz of exactly 5 questions,
based on the article below and the learning chat that followed.
Learner level: {level}

[ARTICLE]
{article_text}

[CHAT LOG FROM THE LEARNING SESSION]
{chat_log}

RULES (QuizSet schema):
- Exactly 5 questions. Each question has exactly 4 choices.
  `answer` must match one of `choices` exactly, character for character.
- **Write everything in English** — question, choices, and explanation.
  The learner is Korean, so keep the wording simple enough for the {level} level,
  but do not switch to Korean.
- **Test English ability, not memory of the story.** Do not ask which country was
  mentioned or what the company announced. Ask what a word means, how a structure
  works, what a phrase implies in context.

QUESTION MIX — follow this exactly:
  Q1, Q2 : VOCABULARY. Pick words that actually appear in the article and quote the
           original sentence fragment they appear in.
  Q3     : GRAMMAR. Quote a sentence from the article and ask about its structure
           (tense, voice, modal, clause type ...).
  Q4     : MEANING IN CONTEXT. An idiom, a figurative phrase, or a word whose meaning
           shifts in this article's context.
  Q5     : **FROM THE CHAT LOG.** Look at what the learner asked about during the chat
           — a word, a phrase, an expression — and turn it into a question.
           Use only chat turns that relate to English or to this article.
           Ignore off-topic chatter (general advice, methodology talk, small talk).
           If the chat log has nothing usable, fall back to one more vocabulary
           question from the article.

DISTRACTORS:
  Same part of speech as the answer, similar length, plausible meaning.
  No 'none of the above', no joke options.

[GOOD EXAMPLE]
  question : In "Criminals ... have attempted to use Anthropic's models",
             what does "attempted" mean?
  choices  : ["tried", "refused", "finished", "forgot"]
  answer   : "tried"
  explanation: "Attempt" means to try to do something. "Refused" is the opposite,
             "finished" means completing it, and "forgot" is unrelated to trying.
"""
