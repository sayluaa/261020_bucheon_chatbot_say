"""자기개발 메이트: 공부·일상 기록·취업 코칭을 한 곳에서 돕는 챗봇."""
import json
import re
from datetime import date

import pandas as pd
import streamlit as st

import storage
from llm import chat

st.set_page_config(page_title="자기개발 메이트", page_icon="🎯", layout="wide")

RECORD_RE = re.compile(r"```record\s*(\{.*?\})\s*```", re.DOTALL)

BASE_PROMPT = (
    "너는 취업을 준비하는 사용자의 자기개발 메이트야. 한국어로, 친근하지만 정확하게 답해. "
    "실시간 정보(채용 공고, 최신 가격 등)는 알 수 없으니 모르면 모른다고 말해.\n"
    "오늘 날짜: {today}\n"
    "[사용자 프로필]\n목표 직무: {job}\n준비 중인 자격증: {certs}\n공부 중인 과목: {studying}\n"
    "[최근 7일 기록]\n{log}\n"
)

MODES = {
    "📚 공부 메이트": (
        "공부를 돕는 모드야. 사용자가 공부 중인 과목에 대해 설명하고, 요청하면 퀴즈를 한 문제씩 내고 채점해. "
        "코딩 질문은 정답을 바로 주기보다 힌트를 먼저 주고, 더 달라고 하면 풀이를 알려줘.\n"
        "사용자가 공부한 시간을 말하면 답변 맨 끝에 아래 형식의 블록을 붙여서 기록해.\n"
        '```record\n{"type": "study", "title": "과목/내용", "minutes": 120}\n```'
    ),
    "📅 일상 기록": (
        "일상 기록 모드야. 사용자가 말한 지출, 일정, 공부 시간을 짧게 확인해주고, "
        "기록할 내용이 있으면 답변 맨 끝에 항목마다 아래 형식의 블록을 붙여. 한 블록에 항목 하나만 넣어.\n"
        '지출: ```record\n{"type": "expense", "title": "점심", "amount": 9000}\n```\n'
        '일정: ```record\n{"type": "schedule", "title": "면접", "when": "2026-10-21 15:00"}\n```\n'
        '공부: ```record\n{"type": "study", "title": "파이썬", "minutes": 90}\n```\n'
        "날짜를 말하지 않으면 오늘 기준으로 처리해. amount와 minutes는 숫자만 써. "
        "'이번 주 어땠어?' 같은 질문에는 최근 기록을 바탕으로 요약하고 조언해."
    ),
    "💼 취업 코치": (
        "취업 코치 모드야. 목표 직무에 맞춰 직무 설명, 자소서 첨삭, 모의 면접을 해. "
        "모의 면접은 질문을 한 번에 하나씩 하고, 답변을 받으면 장점·보완점·점수(10점 만점)를 알려줘. "
        "가능하면 사용자의 최근 공부 기록을 면접 답변 소재로 연결해줘."
    ),
}


def format_log(records: list[dict]) -> str:
    if not records:
        return "(기록 없음)"
    lines = []
    for r in records:
        extra = r.get("minutes") and f"{r['minutes']}분" or r.get("amount") and f"{r['amount']}원" or r.get("when", "")
        lines.append(f"- {r.get('date')} [{r.get('type')}] {r.get('title')} {extra}")
    return "\n".join(lines)


def build_system(mode: str) -> str:
    profile = storage.load_profile()
    base = BASE_PROMPT.format(
        today=date.today().isoformat(),
        job=profile["job"] or "미설정",
        certs=profile["certs"] or "미설정",
        studying=profile["studying"] or "미설정",
        log=format_log(storage.recent_log()),
    )
    return base + "\n" + MODES[mode]


def extract_records(text: str) -> tuple[str, int]:
    """답변에서 record 블록을 꺼내 저장하고, 블록을 뺀 본문과 저장 개수를 반환한다."""
    saved = 0
    for raw in RECORD_RE.findall(text):
        try:
            storage.add_record(json.loads(raw))
            saved += 1
        except json.JSONDecodeError:
            pass
    return RECORD_RE.sub("", text).strip(), saved


def render_sidebar() -> str:
    st.sidebar.title("🎯 자기개발 메이트")
    mode = st.sidebar.radio("모드", list(MODES))

    with st.sidebar.expander("내 목표 설정", expanded=not storage.PROFILE_FILE.exists()):
        profile = storage.load_profile()
        job = st.text_input("목표 직무", profile["job"])
        certs = st.text_input("준비 중인 자격증", profile["certs"])
        studying = st.text_input("공부 중인 과목", profile["studying"])
        if st.button("저장"):
            storage.save_profile({"job": job, "certs": certs, "studying": studying})
            st.rerun()

    st.sidebar.subheader("이번 주 요약")
    records = storage.recent_log()
    df = pd.DataFrame(records)
    study_min = int(df[df["type"] == "study"]["minutes"].sum()) if "minutes" in df else 0
    spent = int(df[df["type"] == "expense"]["amount"].sum()) if "amount" in df else 0
    st.sidebar.metric("공부 시간", f"{study_min // 60}시간 {study_min % 60}분")
    st.sidebar.metric("지출", f"{spent:,}원")

    if st.sidebar.button("현재 모드 대화 지우기"):
        st.session_state.pop(f"chat:{mode}", None)
        st.rerun()
    return mode


def main() -> None:
    mode = render_sidebar()
    st.header(mode)
    key = f"chat:{mode}"
    history = st.session_state.setdefault(key, [])

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("메시지를 입력하세요")
    if not prompt:
        return

    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    messages = [{"role": "system", "content": build_system(mode)}] + history
    with st.chat_message("assistant"):
        with st.spinner("생각 중..."):
            try:
                answer, provider = chat(messages)
            except RuntimeError as err:
                st.error(f"답변을 가져오지 못했어요.\n\n{err}")
                history.pop()
                return
        text, saved = extract_records(answer)
        st.markdown(text)
        notes = [f"모델: {provider}"]
        if saved:
            notes.append(f"{saved}건 기록됨")
        st.caption(" · ".join(notes))

    history.append({"role": "assistant", "content": text})
    if saved:
        st.rerun()


main()
