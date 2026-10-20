# 🎯 자기개발 메이트

취업을 준비하는 사람을 위한 터미널 챗봇입니다. 공부, 일상 기록, 취업 코칭을 한 곳에서 하고,
내 목표 직무와 공부 중인 과목에 맞춰 답해줍니다. (groq API)

## 기능

| 모드 | 하는 일 |
|------|---------|
| 1. 공부 메이트 | 퀴즈 출제·채점, 코딩 질문에 힌트 먼저 제공 |
| 2. 일상 기록 | "점심 9천원", "파이썬 2시간 공부"처럼 말하면 `data/log.json`에 자동 저장 |
| 3. 취업 코치 | 직무 설명, 자소서 첨삭, 모의 면접(질문 → 장점·보완점·점수) |

- 처음 실행하면 목표 직무와 공부 중인 과목을 물어보고 `data/profile.json`에 저장합니다. 이후 모든 모드에 반영됩니다.
- groq 호출이 실패하면(한도 소진 등) gemini로 자동 전환합니다. (`GEMINI_API_KEY` 필요)

## 설치

```bash
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## API 키 설정

`.env.example`을 복사해서 `.env`를 만들고 키를 넣습니다. `.env`는 `.gitignore`에 포함되어 깃에 올라가지 않습니다.

```
GROQ_API_KEY=발급받은_groq_키
GEMINI_API_KEY=발급받은_gemini_키   # 선택: groq 한도 소진 시 폴백
```

## 실행

```bash
python chatbot.py
```

모드 번호를 고르고 대화합니다. 종료는 `exit`.

## 파일 구조

```
chatbot.py        챗봇 본체 (대화 루프, 모드, 기록 저장, gemini 폴백)
data/             profile.json, log.json (자동 생성, 깃 제외)
requirements.txt  필요 라이브러리
streamlit_version/ 웹 UI 버전 (참고용, 추가 설치: pip install streamlit pandas)
```

## 한계

- 모델은 실시간 인터넷 검색을 하지 않습니다. 채용 공고, 최신 가격 같은 정보는 알 수 없습니다.
- 기록은 AI 답변의 `기록:` 줄에서 추출하므로, 가끔 형식이 틀리면 저장되지 않을 수 있습니다.
