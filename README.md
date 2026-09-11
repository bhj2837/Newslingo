# 뉴스링고 (Newslingo)

> 뉴스 기사 기반 개인화 영어 학습 Agent — 6반 5조 AI Agent 설계서 구현체
> LangChain 1.x (`create_agent` + middleware + Structured Output)

사용자가 원하는 주제의 **영문 뉴스**를 추천받아 원문·번역·어휘·문법으로 학습하고,
기사 기반 **자유 대화**와 **퀴즈**로 실력을 점검한다.
난이도는 퀴즈 성과에 따라 **제안만** 되고, 사용자가 **직접 승인(HITL)** 해야만 바뀐다.

---

## 1. 설치 & 실행

```bash
cd 0909-0911_langchain
pip install -r newslingo/requirements.txt

cp newslingo/.env.example newslingo/.env   # 그리고 키 채우기
#  - OPENAI_API_KEY 필수
#  - NEWS_API_KEY 없으면 .env 에서 NEWSLINGO_USE_MOCK_NEWS=true (샘플 기사로 동작)

# 터미널 데모 (설계서 2.2 플로우 전체)
python -m newslingo.app_cli

# 발표/코드리뷰용 워크스루
jupyter notebook newslingo/notebooks/newslingo_demo.ipynb
```

`.env` 는 `newslingo/` 안이든 프로젝트 루트든 두면 자동 로드된다 (`python-dotenv`).

---

## 2. 폴더 구조 — 설계서 섹션과 1:1 대응

| 파일 | 역할 | 설계서 |
|---|---|---|
| `config.py` | 환경변수·모델명·임계치 상수 | 1.5, 2.3 |
| `schemas.py` | Structured Output (Pydantic) | **2.4** |
| `prompts/` | System Prompt / Few-shot / 체인 템플릿 (담당자별 파일 분리) | 2.3 |
| `models.py` | 모델1(메인) / 모델2(분류) 생성 | **2.3** |
| `memory.py` | 단기(checkpointer) / 장기(Store) 메모리 | **3.1** |
| `tools.py` | `news_search`, `update_preference` | **2.5** |
| `guardrails.py` | 입력 1차 규칙 필터 + 2차 분류 모델 | **3.3** |
| `middleware.py` | 프로필 주입 / 요약 / 폴백 / HITL | **3.2** |
| `chains.py` | 기사추천·학습자료·퀴즈 생성 LCEL 체인 | 2.4 |
| `grading.py` | 퀴즈 채점 + 난이도 추천 로직 | 2.2 (10~11) |
| `agent.py` | `create_agent` 조립 (메인 대화 Agent) | **2.1** |
| `service.py` | `LearningSession` — 2.2 플로우 오케스트레이션 | **2.2** |
| `app_cli.py` | 터미널 데모 | — |
| `notebooks/` | 발표용 워크스루 노트북 | — |

---

## 3. UI 붙이는 법 (나중에)

핵심 로직은 전부 `LearningSession` 뒤에 있으므로 UI 는 이것만 쓰면 된다.

```python
from newslingo.service import LearningSession

session = LearningSession(user_id="user_001")     # 사용자당 1개
session.set_initial_level("중급")                  # 0. 온보딩

guard = session.request_topic("LLM 뉴스로 공부하고 싶어")   # 1~2. 가드레일
if guard.allowed:
    cands = session.recommend_articles(guard.extracted_topic)  # 3~4. 기사 5개
    session.select_article(cands.articles[0])                  # 5. 선택
    material = session.make_study_material()                   # 6. 학습자료

    out = session.chat("이 단어 뜻이 뭐야?")                    # 7. 채팅
    if out["interrupt"]:                                       #    HITL 걸리면
        out = session.confirm_preference(approve=True)         #    2차 재확인

    quiz = session.make_quiz()                                 # 8~9. 퀴즈
    result, rec = session.grade(["a", "b", "c", "d", "a"])     # 10~11. 채점+추천
    if rec.is_change():
        out = session.propose_level_change(rec)                # 12. 1차 선택
        out = session.confirm_preference(approve=True)         # 13~14. 2차 재확인
```

- **왜 `.ipynb` 가 아니라 패키지인가?** UI(Streamlit 등)에서 `import` 하려면 모듈이어야 한다.
  노트북(`notebooks/newslingo_demo.ipynb`)은 *발표·코드리뷰용 설명서*로만 두고,
  실제 로직은 이 패키지가 단일 소스(single source of truth)다.

---

## 4. 설계서 대비 구현 메모

- **HITL "2단계 승인"** = UI 버튼 클릭(1차 의사표시) → `HumanInTheLoopMiddleware` interrupt(2차 재확인).
  채팅 중 선호 변경과 **완전히 동일한 메커니즘**을 재사용한다 (설계서 3.2 참고 문구).
- **장기 메모리**: 강의의 `InMemoryStore + managed_keys` 대신 동일 개념을
  namespace/key 를 지원하는 langgraph `Store` 로 구현 (더 간결, `memory.py` 주석 참고).
- **기사/학습자료/퀴즈 생성**은 Agent 가 아니라 `chains.py` 의 LCEL 체인이 담당 →
  Structured Output 품질·재현성 확보 (설계서 2.2 의 "LCEL 체인 호출" 단계).
- **뉴스 소스**: NewsAPI.org 만 사용, 한글 번역은 LLM 직접 수행 (별도 번역 API 없음).
