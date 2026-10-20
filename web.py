from datetime import date, timedelta

import pandas as pd
import streamlit as st

import chatbot as bot  # 터미널 버전의 ask, save_records, make_system, MODES를 그대로 재사용

st.set_page_config(page_title="자기개발 메이트", page_icon="🎯", layout="wide")

# 1. 모드별 화면 설정 (chatbot.MODES의 키와 같은 번호)
STYLE = {
    "1": {
        "icon": "📚", "color": "#4F7CFF",
        "desc": "퀴즈를 풀고, 막히는 코드는 힌트부터 받아보세요."
    },
    "2": {
        "icon": "📅", "color": "#1FB58A",
        "desc": "말하듯 적으면 지출·일정·공부 시간이 자동으로 기록돼요.",
    },
    "3": {
        "icon": "💼", "color": "#E8774A",
        "desc": "직무 설명, 자소서 첨삭, 모의 면접까지 코칭해드려요."
    },
}


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
    for r in bot.load_json(bot.LOG_FILE, []):
        d = r.get("date")
        if d not in df.index:
            continue
        if r.get("type") == "study":
            df.loc[d, "공부(분)"] += to_num(r.get("minutes"))
        elif r.get("type") == "expense":
            df.loc[d, "지출(원)"] += to_num(r.get("amount"))
        elif r.get("type") == "schedule":
            schedules.append(r)
    return df, schedules


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
def chat_tab(mode, profile):
    mode_name, mode_rule = bot.MODES[mode]
    history = st.session_state.setdefault(f"chat:{mode}", [])

    # 직전 답변에서 기록이 저장됐다면 알림 보여주기 (rerun 후에도 남도록 session_state 사용)
    notice = st.session_state.pop("notice", None)
    if notice:
        st.success(notice)

    for msg in history:
        with st.chat_message(msg["role"], avatar=STYLE[mode]["icon"] if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])

    q = st.chat_input("메시지를 입력하세요")
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
        st.session_state["notice"] = f"{saved}건 기록했어요 → '이번 주 기록' 탭에서 확인하세요"
        st.rerun()


# 6. 이번 주 기록 탭
def record_tab():
    df, schedules = week_frame()
    study_min, spent = int(df["공부(분)"].sum()), int(df["지출(원)"].sum())
    c1, c2, c3 = st.columns(3)
    c1.markdown(card("공부 시간", f"{study_min // 60}시간 {study_min % 60}분"), unsafe_allow_html=True)
    c2.markdown(card("지출", f"{spent:,}원"), unsafe_allow_html=True)
    c3.markdown(card("일정", f"{len(schedules)}건"), unsafe_allow_html=True)

    if study_min == 0 and spent == 0 and not schedules:
        st.info("아직 기록이 없어요. '📅 일상 기록' 모드에서 오늘 한 일을 말해보세요!")
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


# 7. 화면 조립
mode, profile = sidebar()
inject_css(STYLE[mode]["color"])
st.markdown(
    f'<div class="hero"><h2>{STYLE[mode]["icon"]} {bot.MODES[mode][0]}</h2><p>{STYLE[mode]["desc"]}</p></div>',
    unsafe_allow_html=True,
)
if profile["job"] == "미설정":
    st.info("왼쪽 '내 목표 설정'에 직무와 공부 과목을 저장하면 답변이 내 목표에 맞춰져요.")

tab_chat, tab_record = st.tabs(["💬 채팅", "📊 이번 주 기록"])
with tab_chat:
    chat_tab(mode, profile)
with tab_record:
    record_tab()
