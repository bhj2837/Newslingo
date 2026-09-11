"""
app.py — 뉴스링고 Streamlit UI

실행:
    streamlit run app.py

디자인: 흰 배경 + oklch 블루 accent, Space Grotesk(헤딩) / Plus Jakarta Sans(본문)
    상단 — 로고 + pill 탭 네비 + 난이도 배지 + 끝내고 퀴즈 보기
    상단2 — 학습 주제 입력 + 추천 기사 5개 카드
    왼쪽(넓게) — 선택한 기사 원문 + 한글 번역
    오른쪽(좁게) — 자유 채팅 + 핵심 단어 / 문법 포인트
    퀴즈 — "끝내고 퀴즈 보기" 클릭 시 별도 화면으로 전환
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# .env 는 원래 newslingo.config 가 import 시점에 읽어들이는데, 그건 이 파일
# 아래쪽에서 일어난다. 목업/실제 모드를 그보다 먼저 판단해야 하므로, 여기서
# 미리 .env 를 로드해 OPENAI_API_KEY 가 실제로 설정돼 있는지부터 확인한다.
load_dotenv(override=True)

# OPENAI_API_KEY 가 없으면 목업 세션(mock_service.py)을 쓴다. 단, chains.py 가
# 모듈 최상단에서 `get_main_model()` 을 호출해 ChatOpenAI 를 즉시 생성하기 때문에,
# 키가 아예 없으면 newslingo 패키지를 import 하는 시점부터 에러가 난다. 목업
# 모드에서는 어차피 그 체인들을 호출하지 않으므로, import 가 깨지지 않도록
# 더미 키를 미리 채워 넣는다 (실제로 API를 부르지는 않는다).
_MOCK_PLACEHOLDER_KEY = "sk-mock-placeholder-not-a-real-key"
_real_key = os.getenv("OPENAI_API_KEY")
USE_MOCK = not _real_key or _real_key == _MOCK_PLACEHOLDER_KEY
if USE_MOCK:
    os.environ["OPENAI_API_KEY"] = _MOCK_PLACEHOLDER_KEY

# 이 파일 자체가 newslingo 패키지 폴더(실제 디스크상 이름은 "Newslingo") 안에
# 있다. service.py 등이 `from . import config` 같은 상대 임포트를 쓰기 때문에,
# 패키지 이름을 "newslingo"로 고정해 sys.modules 에 직접 등록한다 — 폴더 이름의
# 대소문자와 무관하게 항상 동작한다.
_PKG_NAME = "newslingo"
_PKG_DIR = Path(__file__).resolve().parent
if _PKG_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _PKG_NAME, _PKG_DIR / "__init__.py", submodule_search_locations=[str(_PKG_DIR)]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_PKG_NAME] = _module
    _spec.loader.exec_module(_module)

from newslingo import config  # noqa: E402
from newslingo.mock_service import MockLearningSession  # noqa: E402
from newslingo.schemas import LevelRecommendation  # noqa: E402

if not USE_MOCK:
    from newslingo.service import LearningSession  # noqa: E402

st.set_page_config(page_title="뉴스링고", page_icon="📰", layout="wide")

# ──────────────────────────────────────────────────────────────
# 스타일 (아트보드 최종 시안 반영)
# ──────────────────────────────────────────────────────────────
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700&family=Source+Serif+4:wght@600&display=swap');

:root{
  --bg:#fbfbfa; --surface:#ffffff; --ink:#191a1e; --ink-2:#5c5f68; --ink-3:#9698a0;
  --line:#e9e9ec; --accent:oklch(0.55 0.14 258); --accent-soft:oklch(0.96 0.015 258);
}

html, body, [class*="css"] { font-family:'Plus Jakarta Sans','Noto Sans KR',sans-serif; }
.stApp { background: var(--bg); }
h1, h2, h3, .head { font-family:'Space Grotesk','Noto Sans KR',sans-serif !important; letter-spacing:-0.01em; }
#MainMenu, footer, header { visibility:hidden; }
.block-container { padding-top: 1.4rem; max-width: 1360px; }

/* 상단 pill 탭 */
.navbar{ display:flex; align-items:center; justify-content:space-between; margin-bottom:.6rem; }
.navbar .brand{ display:flex; align-items:center; gap:26px; }
.navbar .logo{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:20px; color:var(--ink); }
.navbar .logo .dot{ display:inline-block; width:10px;height:10px;border-radius:3px;background:var(--accent); margin-right:8px; }
.pill-tabs{ display:flex; gap:2px; background:var(--bg); border:1px solid var(--line); border-radius:999px; padding:4px; }
.pill-tabs span{ padding:8px 16px; border-radius:999px; font-size:12.5px; font-weight:600; color:var(--ink-3); }
.pill-tabs span.active{ background:var(--ink); color:#fff; }
.level-badge{ font-size:13px; font-weight:600; color:var(--accent); background:var(--accent-soft);
  border:1px solid var(--line); padding:6px 14px; border-radius:10px; white-space:nowrap;
  display:flex; align-items:center; justify-content:center; text-align:center; }

.tag{ display:inline-block; font-size:10px; font-weight:700; color:var(--ink-2); background:var(--bg);
  padding:3px 9px; border-radius:999px; margin-bottom:8px; }
.tag.accent{ color:var(--accent); background:var(--accent-soft); }

/* 추천 기사 카드 (신문 지면 스타일) */
.news-card{
  display:flex; flex-direction:column; gap:10px; height:100%;
  padding-top:10px; border-top:2px solid var(--ink);
  transition: border-color .15s ease, opacity .15s ease;
}
.news-card .kicker{
  display:flex; align-items:center; justify-content:space-between;
  font-size:10px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3);
}
.news-card .kicker .idx{ font-variant-numeric:tabular-nums; color:var(--ink-3); }
.news-card .kicker .read-badge{
  font-weight:700; letter-spacing:.06em; color:var(--ink-3); background:var(--bg);
  border:1px solid var(--line); border-radius:999px; padding:1px 7px;
}
.news-card .headline{
  font-family:'Source Serif 4', Georgia, 'Noto Serif KR', serif;
  font-size:16.5px; font-weight:600; line-height:1.32; color:var(--ink);
  text-wrap:balance; min-height:62px;
}
.news-card .summary{
  font-size:12.5px; line-height:1.55; color:var(--ink-2);
}
.news-card .byline{
  display:flex; align-items:center; gap:6px; margin-top:auto;
  font-size:11px; color:var(--ink-3); font-variant-numeric:tabular-nums;
  padding-top:8px; border-top:1px solid var(--line);
}
.news-card .byline b{ color:var(--ink-2); font-weight:600; }
.news-card .byline .sep{ opacity:.5; }
.news-card.selected{ border-top-color:var(--accent); }
.news-card.selected .kicker{ color:var(--accent); }
.news-card.selected .headline{ color:var(--ink); }
.news-card.read:not(.selected){ opacity:.5; }
div[data-testid="stHorizontalBlock"]:has(.news-card){ align-items:stretch; }
div[data-testid="stHorizontalBlock"]:has(.news-card) > div{ display:flex; }
div[data-testid="stHorizontalBlock"]:has(.news-card) > div > div{ display:flex; flex-direction:column; width:100%; }
div[data-testid="stElementContainer"]:has(.news-card){ flex:1; display:flex; }

.label{ font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); }

/* 리딩 패널 */
.reading-panel{ background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:22px 26px; }
.reading-title{ font-size:24px; font-weight:700; line-height:1.35; color:var(--ink); margin:10px 0 6px; }
.reading-divider{ border-bottom:1px solid var(--line); margin:8px 0; }
.reading-meta{ font-size:12px; color:var(--ink-3); margin-bottom:14px; }
.reading-body{ padding-top:16px; }
.reading-body p{ font-size:15px; line-height:1.8; color:var(--ink); margin-left:2em; margin-right:2.5em; }
.translation-box{ margin-top:8px; padding:16px; background:var(--bg); border-radius:12px; border:1px dashed var(--line); }

/* 채팅 */
.chat-box{ background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:14px 16px; margin-bottom:16px; }
.bubble-user{ align-self:flex-end; background:var(--accent); color:#fff; padding:9px 14px; border-radius:14px 14px 3px 14px;
  font-size:13px; line-height:1.5; margin:6px 0; max-width:85%; margin-left:auto; }
.bubble-tutor{ background:var(--bg); color:var(--ink-2); padding:9px 14px; border-radius:14px 14px 14px 3px;
  font-size:13px; line-height:1.5; margin:6px 0; max-width:88%; }

/* 단어/문법 */
.vocab-row{ display:flex; flex-direction:column; gap:4px; padding:9px 12px;
  background:var(--bg); border-radius:10px; margin-bottom:6px; font-size:13px; }
.vocab-row-main{ display:flex; justify-content:space-between; align-items:center; }
.vocab-row b{ color:var(--ink); }
.vocab-row-main span{ color:var(--ink-3); font-size:12px; }
.vocab-example{ color:var(--ink-3); font-size:11.5px; font-style:italic; line-height:1.4; }
.grammar-box{ padding:11px 12px; background:var(--accent-soft); border-radius:10px; margin-bottom:6px; }
.grammar-box b{ color:var(--accent); font-size:13px; }
.grammar-box p{ color:var(--ink-2); font-size:12px; line-height:1.5; margin:4px 0 0; }
.grammar-box .grammar-example{ color:var(--ink-3); font-size:11.5px; font-style:italic; margin:6px 0 0; }

/* 채팅 타이핑 인디케이터 */
.bubble-typing{ display:inline-flex; gap:4px; padding:11px 14px; }
.bubble-typing span{ width:6px; height:6px; border-radius:50%; background:var(--ink-3);
  animation: typing-bounce 1s infinite ease-in-out; }
.bubble-typing span:nth-child(2){ animation-delay:.15s; }
.bubble-typing span:nth-child(3){ animation-delay:.3s; }
@keyframes typing-bounce{ 0%, 60%, 100%{ transform:translateY(0); opacity:.4; } 30%{ transform:translateY(-4px); opacity:1; } }

/* 퀴즈 화면 */
:root{ --good:oklch(0.62 0.13 145); --good-soft:oklch(0.96 0.03 145); --bad:oklch(0.62 0.16 25); --bad-soft:oklch(0.96 0.03 25); }
.quiz-question{ font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:15px; color:var(--ink); margin-bottom:2px; }
div[data-testid="stForm"] div[data-testid="stVerticalBlockBorderWrapper"]{
  border-radius:14px !important; border-color:var(--line) !important; margin-bottom:14px;
}
.score-card{
  display:flex; align-items:center; gap:28px; background:var(--surface); border:1px solid var(--line);
  border-radius:18px; padding:26px 30px; margin-bottom:18px;
}
.score-number{ font-family:'Space Grotesk',sans-serif; font-size:44px; font-weight:700; color:var(--accent); line-height:1; white-space:nowrap; }
.score-sub{ font-size:13px; color:var(--ink-3); margin-top:6px; }
.score-label{ font-size:11px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-3); }
.review-row{ display:flex; align-items:flex-start; gap:12px; padding:13px 16px; border-radius:12px;
  background:var(--bg); margin-bottom:8px; border-left:3px solid var(--line); }
.review-row.correct{ border-left-color:var(--good); }
.review-row.wrong{ border-left-color:var(--bad); }
.review-row .review-q{ font-size:13.5px; font-weight:600; color:var(--ink); margin-bottom:4px; }
.review-row .review-a{ font-size:12.5px; color:var(--ink-2); }
.review-row .review-a b{ color:var(--ink); }
.review-row .review-explain{ font-size:12px; color:var(--ink-3); margin-top:4px; line-height:1.5; }
.recommend-card{ background:var(--accent-soft); border:1px solid var(--line); border-radius:16px; padding:20px 24px; margin:18px 0; }
.recommend-card .label{ color:var(--accent); margin-bottom:6px; }
.recommend-card p{ font-size:14px; color:var(--ink); line-height:1.6; margin:0; }

/* 버튼 공통 */
.stButton>button{
  border-radius:10px !important; font-weight:700 !important; font-size:13px !important;
  border:1px solid var(--line) !important;
}
.stButton>button[kind="primary"],
.stFormSubmitButton>button,
.stFormSubmitButton>button[kind="primary"],
.stFormSubmitButton>button[kind="primaryFormSubmit"]{
  background: var(--ink) !important; color:#fff !important; border:none !important;
}
div[class*="st-key-navbar_quiz_btn"] .stButton>button{
  white-space:normal !important; line-height:1.35 !important; padding-top:8px !important; padding-bottom:8px !important;
}
div[class*="st-key-chat_box"]{
  background:var(--surface) !important; border:1px solid var(--line) !important; border-radius:16px !important;
  padding:14px 16px !important; margin-bottom:16px !important;
}

/* 라디오 버튼 선택 색상 (기본 빨강 → 테마 블루) */
.stRadio input[type="radio"]{ accent-color: var(--accent) !important; }
.stRadio label:has(input:checked) > div > div > div:first-child{ background-color: var(--accent) !important; }
.stRadio label:has(input:checked) > div > div > div:first-child > div{ background-color: #fff !important; }

/* 입력창 포커스 색상 (기본 빨강 → 테마 블루) */
.stTextInput input:focus,
.stTextArea textarea:focus{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 1px var(--accent) !important;
}
.stTextInput > div > div:has(input:focus),
.stTextArea > div:has(textarea:focus){
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 1px var(--accent) !important;
}

@media (max-width: 900px){
  .block-container{ padding-left:.6rem; padding-right:.6rem; }
  .navbar{ flex-direction:column; align-items:flex-start; gap:10px; }
}

/* 온보딩 */
.onboard-logo{ display:flex; align-items:center; justify-content:center; gap:10px;
  font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:20px; color:var(--ink); margin-bottom:28px; }
.onboard-logo .dot{ display:inline-block; width:10px;height:10px;border-radius:3px;background:var(--accent); }
.onboard-head{ text-align:center; margin-bottom:36px; }
.onboard-head h1{ font-size:24px; font-weight:700; color:var(--ink); line-height:1.5; margin:0 0 10px; }
.onboard-head .onboard-line2{ display:inline-block; transform:translateX(0.5em); }
.onboard-head p{ font-size:13.5px; font-weight:500; color:var(--ink-2); margin:0; }
.onboard-icon{ font-size:34px; margin-bottom:16px; text-align:center; }
.onboard-title{ font-family:'Space Grotesk',sans-serif; font-size:19px;
  font-weight:700; letter-spacing:-0.01em; color:var(--ink); text-align:center; margin-bottom:22px; }
div[class*="st-key-levelbox_"]{ border-radius:16px !important; border-color:var(--line) !important;
  transition:border-color .15s, box-shadow .15s;
  display:flex !important; flex-direction:column; justify-content:center; align-items:stretch;
  min-height:240px; padding:12px 6px !important; }
div[class*="st-key-levelbox_"]:hover{
  border-color:var(--accent) !important; box-shadow:0 4px 14px -6px oklch(0.55 0.14 258 / .35); }
</style>
"""
st.markdown(STYLE, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# 세션 상태
# ──────────────────────────────────────────────────────────────
def get_session():
    if "session" not in st.session_state:
        if USE_MOCK:
            st.session_state.session = MockLearningSession(user_id="streamlit_user")
        else:
            st.session_state.session = LearningSession(user_id="streamlit_user")
        st.session_state.candidates = []
        st.session_state.study_material = None
        st.session_state.pending_interrupt = None
        st.session_state.show_quiz = False
        st.session_state.quiz = None
        st.session_state.quiz_answers = {}
        st.session_state.quiz_result = None
        st.session_state.level_recommendation = None
        st.session_state.level_interrupt = None
        st.session_state.onboarded = False
        st.session_state.default_candidates_loaded = False
        st.session_state.read_urls = set()
        st.session_state.pending_action = None
        st.session_state.pending_chat_message = None
    return st.session_state.session


session = get_session()


def render_navbar() -> None:
    profile = session.profile
    c1, c2 = st.columns([2.3, 1.7])
    with c1:
        st.markdown(
            """
            <div class="navbar">
              <div class="brand">
                <div class="logo"><span class="dot"></span>뉴스링고</div>
                <div class="pill-tabs"><span class="active">학습</span><span>기록</span></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        cc1, cc2 = st.columns([1, 1.9])
        with cc1:
            st.markdown(
                f'<div class="level-badge" style="margin-top:6px;">{_LEVEL_ICON.get(profile["level"], "📰")} {profile["level"]}</div>',
                unsafe_allow_html=True,
            )
        with cc2, st.container(key="navbar_quiz_btn"):
            if st.button("학습 완료! 퀴즈 응시하기", use_container_width=True, type="primary"):
                if session.current_article is None:
                    st.warning("먼저 기사를 선택해서 학습을 진행해주세요.")
                else:
                    st.session_state.show_quiz = True
                    st.rerun()


# ──────────────────────────────────────────────────────────────
# 0단계: 온보딩
# ──────────────────────────────────────────────────────────────
_LEVEL_ICON = {"초급": "🌱", "중급": "🌿", "고급": "🌳"}


def render_onboarding() -> None:
    lines = [line.strip() for line in session.onboarding_message().split("\n") if line.strip()]
    intro = lines[0] if lines else ""
    prompt_line = lines[1].partition(":")[0].strip() if len(lines) > 1 else ""

    greeting, sep, rest = intro.partition("!")
    title = (
        f'<span class="onboard-line1">{greeting}{sep}</span>'
        f'<br><span class="onboard-line2">{rest.strip()}</span>'
    ) if sep else intro

    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        st.markdown(
            '<div class="onboard-logo"><span class="dot"></span>뉴스링고</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="onboard-head">
              <h1>{title}</h1>
              <p>{prompt_line}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        cols = st.columns(3)
        for col, lvl in zip(cols, config.LEVELS):
            icon = _LEVEL_ICON.get(lvl, "📰")
            with col:
                with st.container(border=True, key=f"levelbox_{lvl}"):
                    st.markdown(
                        f"""
                        <div class="onboard-icon">{icon}</div>
                        <div class="onboard-title">{lvl}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button("이 레벨로 시작", key=f"level_{lvl}", type="primary", use_container_width=True):
                        session.set_initial_level(lvl)
                        st.session_state.onboarded = True
                        st.rerun()


# ──────────────────────────────────────────────────────────────
# 1~4단계: 주제 입력 + 기사 후보
# ──────────────────────────────────────────────────────────────
# 백엔드에 "주제 없이 기본 추천" API가 아직 없어서, 프론트에서 고정 주제로
# 검색을 한 번 자동 실행해 기본 카드 5개를 채운다 (사용자가 직접 "인공지능"을
# 검색한 것과 완전히 동일한 경로 — 가드레일 → recommend_articles). 나중에
# 백엔드에 진짜 "기본 추천" API가 생기면 _run_search() 안의 호출만 바꾸면 됨.
_DEFAULT_TOPIC = "인공지능"


def _run_search(topic: str) -> None:
    guard = session.request_topic(topic)
    if not guard.allowed:
        st.error(session.block_message(guard))
        return
    resolved_topic = guard.extracted_topic or topic
    with st.spinner("주제에 맞는 기사를 찾는 중..."):
        candidates = session.recommend_articles(resolved_topic)
    st.session_state.candidates = list(candidates.articles)
    st.session_state.study_material = None


def _select_article(art) -> None:
    session.select_article(art)
    with st.spinner("학습자료를 만드는 중..."):
        st.session_state.study_material = session.make_study_material()
    st.session_state.read_urls.add(art.url)


def _apply_pending_action() -> None:
    action = st.session_state.pending_action
    st.session_state.pending_action = None
    st.session_state.show_quiz = False
    st.session_state.quiz = None
    st.session_state.quiz_answers = {}
    st.session_state.quiz_result = None
    st.session_state.level_recommendation = None
    st.session_state.level_interrupt = None
    if action is None:
        return
    if action["type"] == "article":
        art = next((a for a in st.session_state.candidates if a.url == action["url"]), None)
        if art is not None:
            _select_article(art)
    elif action["type"] == "search":
        _run_search(action["topic"])


def render_topic_and_candidates() -> None:
    if not st.session_state.candidates and not st.session_state.get("default_candidates_loaded"):
        st.session_state.default_candidates_loaded = True
        _run_search(_DEFAULT_TOPIC)
        st.rerun()

    col1, col2 = st.columns([5, 1])
    with col1:
        topic_input = st.text_input(
            "topic", placeholder="오늘의 학습 주제를 입력하세요 — 예: 인공지능, 기후변화, 우주 탐사",
            label_visibility="collapsed",
        )
    with col2:
        search_clicked = st.button("기사 찾기", use_container_width=True, type="primary")

    if search_clicked and topic_input.strip():
        if session.current_article is not None:
            # 기사를 읽던 중 다른 주제를 검색하면, 퀴즈를 먼저 풀어야 넘어갈 수 있다.
            st.session_state.pending_action = {"type": "search", "topic": topic_input.strip()}
            st.session_state.show_quiz = True
        else:
            _run_search(topic_input.strip())
        st.rerun()

    if st.session_state.candidates:
        st.markdown('<div class="label" style="margin:14px 0 8px;">추천 기사</div>', unsafe_allow_html=True)
        cols = st.columns(5)
        selected_url = (session.current_article or {}).get("url")
        for i, (col, art) in enumerate(zip(cols, st.session_state.candidates), start=1):
            with col:
                is_selected = art.url == selected_url
                is_read = art.url in st.session_state.read_urls
                category = (art.keywords[0] if art.keywords else art.source).title()
                idx_html = '<span class="read-badge">읽음</span>' if is_read and not is_selected else f'<span class="idx">{i:02d}</span>'
                card_classes = "news-card"
                if is_selected:
                    card_classes += " selected"
                if is_read:
                    card_classes += " read"
                st.markdown(
                    f"""
                    <div class="{card_classes}">
                      <div class="kicker"><span>{category}</span>{idx_html}</div>
                      <div class="headline">{art.title}</div>
                      <div class="summary">{art.summary}</div>
                      <div class="byline"><b>{art.source}</b><span class="sep">·</span><span>{art.published_date}</span></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if is_selected:
                    btn_label = "읽는 중"
                elif is_read:
                    btn_label = "다시 읽기"
                else:
                    btn_label = "읽기"
                if st.button(btn_label, key=f"pick-{art.url}", use_container_width=True, disabled=is_selected):
                    if session.current_article is not None:
                        # 다른 기사를 읽던 중이면, 퀴즈를 먼저 풀어야 넘어갈 수 있다.
                        st.session_state.pending_action = {"type": "article", "url": art.url}
                        st.session_state.show_quiz = True
                    else:
                        _select_article(art)
                    st.rerun()


# ──────────────────────────────────────────────────────────────
# 5~6단계 + 7단계: 리딩 패널 + 채팅 + 단어/문법
# ──────────────────────────────────────────────────────────────
def render_learning_area() -> None:
    article = session.current_article
    material = st.session_state.study_material
    if article is None or material is None:
        return

    left, right = st.columns([2.1, 1])

    with left:
        body_paragraphs = "".join(
            f"<p>{para.strip()}</p>"
            for para in article["text"].split("\n\n")[:6]
            if para.strip()
        )
        translated_html = "<br><br>".join(
            line.strip() for line in material.translated_text.split("\n\n") if line.strip()
        )
        st.markdown(
            f"""
            <div class="reading-panel">
              <span class="tag accent">Article</span>
              <div class="reading-title">{article['title']}</div>
              <div class="reading-divider"></div>
              <div class="reading-meta">{article.get('source', '')} · {article.get('date', '')}</div>
              <div class="reading-body">
                {body_paragraphs}
                <div class="translation-box">
                  <div class="label" style="color:var(--accent);margin-bottom:8px;">한글 번역</div>
                  <p style="color:var(--ink-2);font-size:14.5px;line-height:1.75;margin-left:1em;margin-right:0;">{translated_html}</p>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        render_vocab_grammar(material)
        render_chat()


def render_chat() -> None:
    with st.container(border=True, key="chat_box"):
        st.markdown('<div class="label" style="margin-bottom:8px;">질문하며 학습하기</div>', unsafe_allow_html=True)

        pending_msg = st.session_state.get("pending_chat_message")

        history_box = st.container(height=440, key="chat_history")
        with history_box:
            for line in session.chat_log:
                if line.startswith("User: "):
                    st.markdown(f'<div class="bubble-user">{line[6:]}</div>', unsafe_allow_html=True)
                elif line.startswith("Tutor: "):
                    st.markdown(f'<div class="bubble-tutor">{line[7:]}</div>', unsafe_allow_html=True)
            if pending_msg is not None:
                st.markdown(f'<div class="bubble-user">{pending_msg}</div>', unsafe_allow_html=True)
                st.markdown(
                    '<div class="bubble-tutor bubble-typing"><span></span><span></span><span></span></div>',
                    unsafe_allow_html=True,
                )

        # 스크롤 스크립트는 srcdoc 이 바뀔 때만 다시 실행된다. 내용이 매번 같으면
        # Streamlit 이 iframe 을 재마운트하지 않아 최초 1회만 돌고 끝난다.
        # 대화가 늘어날 때마다 값이 바뀌는 토큰을 넣어 강제로 다시 마운트시킨다.
        _scroll_token = f"{len(session.chat_log)}-{1 if pending_msg is not None else 0}"
        components.html(
            """
            <script>
            (function(){
              const doc = window.parent.document;
              const root = doc.querySelector('.st-key-chat_history');
              if (!root) return;
              function findScrollable(el){
                if (el.scrollHeight > el.clientHeight) return el;
                for (const child of el.children){
                  const found = findScrollable(child);
                  if (found) return found;
                }
                return null;
              }
              // 말풍선 레이아웃이 끝나야 scrollHeight 가 확정되므로,
              // 몇 프레임에 걸쳐 반복해서 바닥에 붙인다.
              let tries = 0;
              (function stick(){
                const target = findScrollable(root) || root;
                target.scrollTop = target.scrollHeight;
                if (++tries < 15) requestAnimationFrame(stick);
              })();
            })();
            </script>
            <!-- scroll-token: TOKEN -->
            """.replace("TOKEN", _scroll_token),
            height=0,
        )

        if pending_msg is not None:
            # 이전 rerun에서 사용자 말풍선 + 타이핑 표시까지 먼저 그려둔 뒤,
            # 이번 run에서 실제로 응답을 생성한다 (지연 시간 동안 UI가 비어있지 않도록).
            out = session.chat(pending_msg)
            st.session_state.pending_chat_message = None
            st.session_state.pending_interrupt = out["interrupt"]
            st.rerun()
            return

        interrupt = st.session_state.pending_interrupt
        if interrupt is not None:
            st.info(f"🔔 확인 필요: {interrupt}")
            c1, c2 = st.columns(2)
            if c1.button("승인", key="chat-approve", use_container_width=True, type="primary"):
                out = session.confirm_preference(approve=True)
                st.session_state.pending_interrupt = out["interrupt"]
                st.rerun()
            if c2.button("거절", key="chat-reject", use_container_width=True):
                out = session.confirm_preference(approve=False)
                st.session_state.pending_interrupt = out["interrupt"]
                st.rerun()
        else:
            with st.form("chat-form", clear_on_submit=True):
                msg = st.text_input("msg", placeholder="질문을 입력하세요...", label_visibility="collapsed")
                sent = st.form_submit_button("전송", use_container_width=True, type="primary")
            if sent and msg.strip():
                st.session_state.pending_chat_message = msg.strip()
                st.rerun()


def render_vocab_grammar(material) -> None:
    st.markdown('<div class="label" style="margin-bottom:10px;">핵심 단어</div>', unsafe_allow_html=True)
    for term in material.basic_vocab:
        st.markdown(
            f"""
            <div class="vocab-row">
              <div class="vocab-row-main"><b>{term.term}</b><span>{term.meaning}</span></div>
              <div class="vocab-example">"{term.example}"</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('<div class="label" style="margin:14px 0 10px;">전문 용어</div>', unsafe_allow_html=True)
    for term in material.key_terms:
        st.markdown(
            f"""
            <div class="vocab-row">
              <div class="vocab-row-main"><b>{term.term}</b><span>{term.meaning}</span></div>
              <div class="vocab-example">"{term.example}"</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('<div class="label" style="margin:14px 0 10px;">문법 포인트</div>', unsafe_allow_html=True)
    for g in material.grammar_points:
        st.markdown(
            f"""
            <div class="grammar-box">
              <b>{g.pattern}</b>
              <p>{g.explanation}</p>
              <p class="grammar-example">"{g.example}"</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────
# 8~14단계: 퀴즈 화면 (별도 화면)
# ──────────────────────────────────────────────────────────────
def render_quiz_screen() -> None:
    forced = st.session_state.pending_action is not None
    st.markdown('<p class="head" style="font-size:24px;font-weight:700;">📝 퀴즈</p>', unsafe_allow_html=True)
    if forced:
        st.caption("🔒 다른 기사로 넘어가려면 먼저 퀴즈를 완료해주세요.")
    elif st.button("← 학습으로 돌아가기"):
        st.session_state.show_quiz = False
        st.rerun()

    if st.session_state.quiz is None:
        with st.spinner("퀴즈를 만드는 중..."):
            st.session_state.quiz = session.make_quiz()
        st.session_state.quiz_answers = {}
        st.session_state.quiz_result = None

    quiz = st.session_state.quiz

    if st.session_state.quiz_result is None:
        with st.form("quiz-form"):
            for i, q in enumerate(quiz.questions):
                with st.container(border=True):
                    st.markdown(f'<div class="quiz-question">Q{i + 1}. {q.question}</div>', unsafe_allow_html=True)
                    st.session_state.quiz_answers[i] = st.radio(
                        f"q{i}", q.choices, key=f"quiz-q-{i}", label_visibility="collapsed"
                    )
            submitted = st.form_submit_button("채점하기", type="primary")
        if submitted:
            answers = [st.session_state.quiz_answers[i] for i in range(len(quiz.questions))]
            result, recommendation = session.grade(answers)
            st.session_state.quiz_result = result
            st.session_state.level_recommendation = recommendation
            st.rerun()
        return

    result = st.session_state.quiz_result
    recommendation: LevelRecommendation = st.session_state.level_recommendation

    st.markdown(
        f"""
        <div class="score-card">
          <div class="score-number">{result.correct}/{result.total}</div>
          <div>
            <div class="score-label">채점 완료</div>
            <div class="score-sub">정답률 {result.accuracy:.0%} — 아래에서 문항별 결과를 확인하세요.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for d in result.details:
        row_class = "correct" if d.is_correct else "wrong"
        icon = "✅" if d.is_correct else "❌"
        explain_html = (
            f'<div class="review-explain">내 답: {d.user_answer} · {d.explanation}</div>'
            if not d.is_correct
            else ""
        )
        st.markdown(
            f"""
            <div class="review-row {row_class}">
              <span>{icon}</span>
              <div style="flex:1;">
                <div class="review-q">{d.question}</div>
                <div class="review-a">정답: <b>{d.correct_answer}</b></div>
                {explain_html}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="recommend-card">
          <div class="label">추천</div>
          <p>{recommendation.message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    continue_label = "다음 기사로 계속하기 →" if forced else "← 학습으로 돌아가기"

    interrupt = st.session_state.level_interrupt
    if interrupt is not None:
        st.info(f"🔔 확인 필요: {interrupt}")
        c1, c2 = st.columns(2)
        if c1.button("승인", key="level-approve", type="primary"):
            out = session.confirm_preference(approve=True)
            st.session_state.level_interrupt = out["interrupt"]
            if out["interrupt"] is None:
                st.rerun()
        if c2.button("거절", key="level-reject"):
            out = session.confirm_preference(approve=False)
            st.session_state.level_interrupt = out["interrupt"]
            st.rerun()
    elif recommendation.is_change():
        c1, c2 = st.columns(2)
        if c1.button(f"{recommendation.suggested_level}(으)로 변경", type="primary"):
            out = session.request_level_change(recommendation.suggested_level)
            st.session_state.level_interrupt = out["interrupt"]
            st.rerun()
        if c2.button(f"현재 난이도 유지 · {continue_label}"):
            _apply_pending_action()
            st.rerun()
    else:
        if st.button(continue_label, type="primary"):
            _apply_pending_action()
            st.rerun()


# ──────────────────────────────────────────────────────────────
# 엔트리
# ──────────────────────────────────────────────────────────────
if not st.session_state.onboarded:
    render_onboarding()
elif st.session_state.show_quiz:
    render_quiz_screen()
else:
    render_navbar()
    render_topic_and_candidates()
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    render_learning_area()
