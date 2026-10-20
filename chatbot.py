from dotenv import load_dotenv
import os
import json
import httpx
from datetime import date
from groq import Groq
from termcolor import colored

# 1. 환경 변수 불러오기
load_dotenv()

# 2. 클라이언트 만들기(Groq API 요청)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 3. 저장 파일 경로
os.makedirs("data", exist_ok=True)
PROFILE_FILE = "data/profile.json"
LOG_FILE = "data/log.json"

# 4. 모드별 AI 성격 및 규칙
MODES = {
    "1": ("공부 메이트", "공부를 도와줘. 퀴즈는 한 문제씩 내고 채점해줘. 코딩 질문은 힌트를 먼저 주고, 더 달라고 하면 풀이를 알려줘."),
    "2": ("일상 기록", "사용자가 말한 지출, 일정, 공부 시간을 짧게 확인해줘. "
                      "기록할 내용이 있으면 답변 맨 끝에 한 줄씩 아래 형식으로 붙여줘. "
                      '기록: {"type": "expense", "title": "점심", "amount": 9000} '
                      '기록: {"type": "study", "title": "파이썬", "minutes": 90} '
                      '기록: {"type": "schedule", "title": "면접", "when": "2026-10-21 15:00"} '
                      "amount와 minutes는 숫자만 써."),
    "3": ("취업 코치", "취업 코치야. 직무 설명, 자소서 첨삭, 모의 면접을 해줘. "
                      "면접은 질문을 하나씩 하고, 답변을 받으면 장점, 보완점, 점수(10점 만점)를 알려줘."),
}


# 5. 파일 읽기/쓰기 함수
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 6. groq가 실패하면 gemini로 질문 보내는 함수
def ask_gemini(messages):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY가 .env에 없습니다")
    system = messages[0]["content"]
    contents = []
    for m in messages[1:]:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
    res = httpx.post(
        url,
        headers={"x-goog-api-key": key},
        json={"system_instruction": {"parts": [{"text": system}]}, "contents": contents},
        timeout=60,
    )
    res.raise_for_status()
    return res.json()["candidates"][0]["content"]["parts"][0]["text"]


def ask(messages):
    try:
        res = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.7,
        )
        return res.choices[0].message.content
    except Exception as e:
        print(colored(f"(groq 실패 -> gemini로 전환: {e})", "yellow"))
        return ask_gemini(messages)


# 7. 답변에서 '기록:' 줄을 찾아 저장하고, 나머지 본문만 돌려주는 함수
def save_records(answer):
    log = load_json(LOG_FILE, [])
    lines = []
    for line in answer.split("\n"):
        if line.strip().startswith("기록:"):
            try:
                record = json.loads(line.strip()[3:])
                record["date"] = date.today().isoformat()
                log.append(record)
                print(colored(f"[저장됨] {record}", "green"))
            except json.JSONDecodeError:
                pass
        else:
            lines.append(line)
    save_json(LOG_FILE, log)
    return "\n".join(lines).strip()


# 8. 프로필(목표) 불러오기, 없으면 입력받기
profile = load_json(PROFILE_FILE, {})
if not profile:
    profile["job"] = input("목표 직무 : ")
    profile["studying"] = input("공부 중인 과목 : ")
    save_json(PROFILE_FILE, profile)

# 9. 모드 선택
print("1. 공부 메이트  2. 일상 기록  3. 취업 코치")
mode = input("모드 선택 : ")
if mode not in MODES:
    mode = "1"
mode_name, mode_rule = MODES[mode]

# 10. 대화 기록 맨 앞에 AI 성격 및 규칙 지정
messages = [
    {
        "role": "system",
        "content": (
            f"너는 취업을 준비하는 사용자의 자기개발 메이트야. 한국어로 답해줘. "
            f"실시간 정보는 모르니까 모르면 모른다고 말해줘. "
            f"오늘 날짜는 {date.today().isoformat()}이야. "
            f"사용자의 목표 직무는 {profile['job']}이고 공부 중인 과목은 {profile['studying']}이야. "
            f"[{mode_name} 모드] {mode_rule}"
        ),
    }
]
print(f"\n[{mode_name}] 시작! 종료는 exit\n")

# 11. 대화 진행 및 종료 입력 설정
while True:
    # 11-1. 질문
    q = input("나 : ")
    # 11-2. 종료 입력
    if q == "exit":
        print("대화를 종료합니다")
        break
    # 11-3. 질문을 대화 기록에 추가
    messages.append(
        {
            "role": "user",
            "content": q
        }
    )
    # 11-4. 질문 보내고 답변 받기
    answer = ask(messages)
    # 11-5. '기록:' 줄 저장하고 본문만 출력
    text = save_records(answer)
    print(colored(f"메이트 : {text}", "cyan"))
    # 11-6. AI 답도 기록에 추가
    messages.append(
        {
            "role": "assistant",
            "content": text
        }
    )
