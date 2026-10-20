from datetime import date, timedelta
from urllib.parse import quote

import pandas as pd
import streamlit as st

import chatbot as bot  # 터미널 버전의 ask, save_records, make_system, MODES를 그대로 재사용

st.set_page_config(page_title="자기개발 메이트", page_icon="🎯", layout="wide")

# 1. 모드별 화면 설정 (chatbot.MODES의 키와 같은 번호)
STYLE = {
    "1": {
        "icon": "📚", "color": "#4F7CFF", "tab": "📊 공부 기록",
        "desc": "퀴즈를 풀고, 막히는 코드는 힌트부터 받아보세요."
    },
    "2": {
        "icon": "📅", "color": "#1FB58A", "tab": "📊 이번 주 기록",
        "desc": "말하듯 적으면 지출·일정·공부 시간이 자동으로 기록돼요.",
    },
    "3": {
        "icon": "💼", "color": "#E8774A", "tab": "📊 취업 준비",
        "desc": "직무 설명, 자소서 첨삭, 모의 면접까지 코칭해드려요."
    },
}

LEVEL = {"easy": "쉬움", "medium": "보통", "hard": "어려움"}


# 2. 기록을 최근 7일 표로 만드는 함수
def to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def week_frame():
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    df = pd.DataFrame({"날짜": days, "공부(분)": 0.0, "지출(원)": 0.0}).set_index("날짜")
    schedules = []
    subjects = {}  # 과목별 공부 시간(분)
    for r in bot.load_json(bot.LOG_FILE, []):
        d = r.get("date")
        if d not in df.index:
            continue
        if r.get("type") == "study":
            df.loc[d, "공부(분)"] += to_num(r.get("minutes"))
            subjects[r.get("title", "기타")] = subjects.get(r.get("title", "기타"), 0) + to_num(r.get("minutes"))
        elif r.get("type") == "expense":
            df.loc[d, "지출(원)"] += to_num(r.get("amount"))
        elif r.get("type") == "schedule":
            schedules.append(r)
    return df, schedules, subjects


def records_of(kind):
    return [r for r in bot.load_json(bot.LOG_FILE, []) if r.get("type") == kind]


def d_day(deadline):
    """'2026-11-15' -> 'D-26' / '오늘 마감' / '마감됨' / '-'"""
    try:
        days = (date.fromisoformat(deadline) - date.today()).days
    except (TypeError, ValueError):
        return "-"
    if days < 0:
        return "마감됨"
    return "오늘 마감" if days == 0 else f"D-{days}"


# 3. 사이드바: 제목, 모드 선택, 목표 설정
def sidebar():
    st.sidebar.markdown("## 🎯 자기개발 메이트")
    st.sidebar.caption("공부 · 일상 기록 · 취업 코칭")
    mode = st.sidebar.radio(
        "모드",
        list(bot.MODES),
        format_func=lambda k: f"{STYLE[k]['icon']} {bot.MODES[k][0]}",
    )

    profile = bot.load_json(bot.PROFILE_FILE, {})
    with st.sidebar.expander("내 목표 설정", expanded=not profile):
        with st.form("profile"):
            job = st.text_input("목표 직무", profile.get("job", ""))
            studying = st.text_input("공부 중인 과목", profile.get("studying", ""))
            if st.form_submit_button("저장", use_container_width=True):
                bot.save_json(bot.PROFILE_FILE, {"job": job, "studying": studying})
                st.rerun()

    if st.sidebar.button("이 모드 대화 지우기", use_container_width=True):
        st.session_state.pop(f"chat:{mode}", None)
        st.rerun()
    return mode, {"job": profile.get("job") or "미설정", "studying": profile.get("studying") or "미설정"}


# 4. 화면 꾸미기 (CSS). 라이트/다크 모두에서 보이도록 반투명 배경 사용
def inject_css(color):
    st.markdown(
        f"""
        <style>
        .hero {{
            background: linear-gradient(135deg, {color}, {color}aa);
            color: white; padding: 1.4rem 1.6rem; border-radius: 18px; margin-bottom: 1rem;
        }}
        .hero h2 {{ margin: 0 0 .3rem 0; color: white; }}
        .hero p {{ margin: 0; opacity: .92; }}
        .card {{
            background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.2);
            border-left: 5px solid {color}; border-radius: 14px; padding: .9rem 1.1rem;
        }}
        .card .label {{ font-size: .85rem; opacity: .7; }}
        .card .value {{ font-size: 1.6rem; font-weight: 700; }}
        div[data-testid="stChatMessage"] {{ border-radius: 16px; padding: .6rem .9rem; }}
        .stButton > button {{ border-radius: 999px; border: 1px solid {color}66; }}
        .stButton > button:hover {{ border-color: {color}; color: {color}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(label, value):
    return f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>'


# 5. 채팅 탭
def chat_tab(mode, profile, q):
    mode_name, mode_rule = bot.MODES[mode]
    history = st.session_state.setdefault(f"chat:{mode}", [])

    # 직전 답변에서 기록이 저장됐다면 알림 보여주기 (rerun 후에도 남도록 session_state 사용)
    notice = st.session_state.pop("notice", None)
    if notice:
        st.success(notice)

    for msg in history:
        with st.chat_message(msg["role"], avatar=STYLE[mode]["icon"] if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])

    if not q:
        return

    with st.chat_message("user"):
        st.markdown(q)
    history.append({"role": "user", "content": q})

    # 터미널 버전과 같은 방식: 맨 앞에 system, 그 뒤에 대화 기록
    messages = [{"role": "system", "content": bot.make_system(profile, mode_name, mode_rule)}] + history
    with st.chat_message("assistant", avatar=STYLE[mode]["icon"]):
        with st.spinner("생각 중..."):
            before = len(bot.load_json(bot.LOG_FILE, []))
            try:
                answer = bot.ask(messages)
            except Exception as e:
                history.pop()
                st.error(f"답변을 가져오지 못했어요: {e}")
                return
            text = bot.save_records(answer)
            saved = len(bot.load_json(bot.LOG_FILE, [])) - before
        st.markdown(text)

    history.append({"role": "assistant", "content": text})
    if saved:
        st.session_state["notice"] = f"{saved}건 기록했어요 → '{STYLE[mode]['tab']}' 탭에서 확인하세요"
        st.rerun()


# 6-1. 공부 메이트 탭: 공부 시간만 (지출 없음)
def study_tab():
    df, _, subjects = week_frame()
    study_min = int(df["공부(분)"].sum())
    days = int((df["공부(분)"] > 0).sum())
    c1, c2, c3 = st.columns(3)
    c1.markdown(card("이번 주 공부 시간", f"{study_min // 60}시간 {study_min % 60}분"), unsafe_allow_html=True)
    c2.markdown(card("공부한 날", f"{days}일"), unsafe_allow_html=True)
    c3.markdown(card("공부한 과목", f"{len(subjects)}개"), unsafe_allow_html=True)

    if study_min == 0:
        st.info("아직 기록이 없어요. 채팅에서 \"파이썬 2시간 공부했어\"처럼 말하면 기록돼요!")
        return

    left, right = st.columns(2)
    left.markdown("**일별 공부 시간 (분)**")
    left.bar_chart(df["공부(분)"], color="#4F7CFF")
    right.markdown("**과목별 공부 시간 (분)**")
    right.bar_chart(pd.Series(subjects, name="공부(분)"), color="#4F7CFF")


# 6-2. 일상 기록 탭: 공부 + 지출 + 일정
def daily_tab():
    df, schedules, _ = week_frame()
    study_min, spent = int(df["공부(분)"].sum()), int(df["지출(원)"].sum())
    c1, c2, c3 = st.columns(3)
    c1.markdown(card("공부 시간", f"{study_min // 60}시간 {study_min % 60}분"), unsafe_allow_html=True)
    c2.markdown(card("지출", f"{spent:,}원"), unsafe_allow_html=True)
    c3.markdown(card("일정", f"{len(schedules)}건"), unsafe_allow_html=True)

    if study_min == 0 and spent == 0 and not schedules:
        st.info("아직 기록이 없어요. 오늘 한 일을 말해보세요!")
        return

    left, right = st.columns(2)
    left.markdown("**일별 공부 시간 (분)**")
    left.bar_chart(df["공부(분)"], color="#4F7CFF")
    right.markdown("**일별 지출 (원)**")
    right.bar_chart(df["지출(원)"], color="#1FB58A")

    if schedules:
        st.markdown("**일정**")
        st.dataframe(
            pd.DataFrame(schedules)[["date", "title", "when"]].rename(columns={"date": "기록일", "title": "내용", "when": "일시"}),
            hide_index=True, use_container_width=True,
        )


# 6-3. 취업 코치 탭: 일정 + 공고 + 추천 자격증
def career_tab(profile):
    jobs = sorted(records_of("job"), key=lambda r: r.get("deadline") or "9999-99-99")
    schedules = sorted(records_of("schedule"), key=lambda r: r.get("when") or "")
    certs = records_of("cert")

    c1, c2, c3 = st.columns(3)
    c1.markdown(card("저장한 공고", f"{len(jobs)}건"), unsafe_allow_html=True)
    c2.markdown(card("일정", f"{len(schedules)}건"), unsafe_allow_html=True)
    c3.markdown(card("추천 자격증", f"{len(certs)}개"), unsafe_allow_html=True)

    # 목표 직무로 바로 검색하는 링크 (실시간 공고는 AI가 볼 수 없어서 사이트로 연결)
    target = profile["job"].split(",")[0].strip()
    st.markdown("**채용 공고 찾기**")
    b1, b2, _ = st.columns([1, 1, 3])
    b1.link_button("사람인", f"https://www.saramin.co.kr/zf_user/search?searchword={quote(target)}",
                   disabled=target == "미설정", use_container_width=True)
    b2.link_button("잡코리아", f"https://www.jobkorea.co.kr/Search/?stext={quote(target)}",
                   disabled=target == "미설정", use_container_width=True)
    st.caption("마음에 드는 공고 내용을 채팅에 붙여넣으면 회사·직무·마감일을 정리해서 아래에 저장해요.")

    st.markdown("**저장한 공고 (마감 임박순)**")
    if jobs:
        st.dataframe(
            pd.DataFrame([
                {"마감": d_day(r.get("deadline")), "회사": r.get("company", ""), "직무": r.get("title", ""),
                 "마감일": r.get("deadline") or "-", "메모": r.get("note", "")}
                for r in jobs
            ]),
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("아직 저장한 공고가 없어요.")

    st.markdown("**일정**")
    if schedules:
        st.dataframe(
            pd.DataFrame([{"일시": r.get("when", ""), "내용": r.get("title", "")} for r in schedules]),
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("면접·서류 마감 같은 일정을 말하면 여기에 모여요.")

    st.markdown("**추천 자격증**")
    if certs:
        st.dataframe(
            pd.DataFrame([
                {"자격증": r.get("name", ""), "난이도": LEVEL.get(r.get("level"), "-"), "추천 이유": r.get("reason", "")}
                for r in certs
            ]),
            hide_index=True, use_container_width=True,
        )
        st.caption("AI의 일반 지식이라 시험 일정·응시료는 틀릴 수 있어요. 큐넷(q-net.or.kr) 등 공식 사이트에서 꼭 확인하세요.")
    else:
        st.info("채팅에서 \"내 직무에 맞는 자격증 추천해줘\"라고 말해보세요.")


def record_tab(mode, profile):
    if mode == "1":
        study_tab()
    elif mode == "2":
        daily_tab()
    else:
        career_tab(profile)


# 7. 화면 조립
mode, profile = sidebar()
inject_css(STYLE[mode]["color"])
st.markdown(
    f'<div class="hero"><h2>{STYLE[mode]["icon"]} {bot.MODES[mode][0]}</h2><p>{STYLE[mode]["desc"]}</p></div>',
    unsafe_allow_html=True,
)
if profile["job"] == "미설정":
    st.info("왼쪽 '내 목표 설정'에 직무와 공부 과목을 저장하면 답변이 내 목표에 맞춰져요.")

# 입력창은 탭 밖(최상위)에 둬야 화면 하단에 고정되어 스크롤해도 위치가 바뀌지 않는다
q = st.chat_input("메시지를 입력하세요")

tab_chat, tab_record = st.tabs(["💬 채팅", STYLE[mode]["tab"]])
with tab_chat:
    chat_tab(mode, profile, q)
with tab_record:
    record_tab(mode, profile)
