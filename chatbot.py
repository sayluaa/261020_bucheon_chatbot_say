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

# 4. 모드별 AI 성격 및 규칙 (페르소나는 영어로 작성, 답변은 한국어로 하도록 지시)
MODES = {
    "1": ("공부 메이트", "You are a study mate. Quiz the user one question at a time and grade the answer. "
                      "For coding questions, give a hint first, and give the full solution only when the user asks for more."),
    "2": ("일상 기록", "You are a daily log assistant. Briefly confirm the expenses, schedules, and study time the user mentions. "
                      "If there is anything to record, append one line per item at the very end of your reply in this format: "
                      'RECORD: {"type": "expense", "title": "lunch", "amount": 9000} '
                      'RECORD: {"type": "study", "title": "Python", "minutes": 90} '
                      'RECORD: {"type": "schedule", "title": "interview", "when": "2026-10-21 15:00"} '
                      "Use plain numbers only for amount and minutes. Write each title in Korean. "
                      "Never put anything else on a RECORD line."),
    "3": ("취업 코치", "You are a strict but supportive career coach. Explain job roles, review cover letters, and run mock interviews. "
                      "In a mock interview, ask one question at a time; after each answer, give strengths, areas to improve, "
                      "and a score out of 10."),
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
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent"
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


# 7. 답변에서 'RECORD:' 줄을 찾아 저장하고, 나머지 본문만 돌려주는 함수
def save_records(answer):
    log = load_json(LOG_FILE, [])
    lines = []
    for line in answer.split("\n"):
        if line.strip().startswith("RECORD:"):
            try:
                record = json.loads(line.strip()[len("RECORD:"):])
                record["date"] = date.today().isoformat()
                log.append(record)
                print(colored(f"[저장됨] {record}", "green"))
            except json.JSONDecodeError:
                pass
        else:
            lines.append(line)
    save_json(LOG_FILE, log)
    return "\n".join(lines).strip()


# 8. 프로필과 모드를 받아 시스템 프롬프트(AI 성격 및 규칙) 만드는 함수
def make_system(profile, mode_name, mode_rule):
    return (
        "You are a self-development mate for a user preparing for a job. "
        "Always reply in Korean, in a friendly tone. "
        "You cannot access real-time information, so say so honestly when you don't know. "
        f"Today's date is {date.today().isoformat()}. "
        f"The user's target job is {profile['job']} and the subjects they are studying are {profile['studying']}. "
        f"[Mode: {mode_name}] {mode_rule}"
    )


def main():
    # 9. 프로필(목표) 불러오기, 없으면 입력받기
    profile = load_json(PROFILE_FILE, {})
    if not profile:
        profile["job"] = input("목표 직무 : ")
        profile["studying"] = input("공부 중인 과목 : ")
        save_json(PROFILE_FILE, profile)

    # 10. 모드 선택
    print("1. 공부 메이트  2. 일상 기록  3. 취업 코치")
    mode = input("모드 선택 : ")
    if mode not in MODES:
        mode = "1"
    mode_name, mode_rule = MODES[mode]

    # 11. 대화 기록 맨 앞에 AI 성격 및 규칙 지정
    messages = [
        {
            "role": "system",
            "content": make_system(profile, mode_name, mode_rule),
        }
    ]
    print(f"\n[{mode_name}] 시작! 종료는 exit\n")

    # 12. 대화 진행 및 종료 입력 설정
    while True:
        # 12-1. 질문
        q = input("나 : ")
        # 12-2. 종료 입력
        if q == "exit":
            print("대화를 종료합니다")
            break
        # 12-3. 질문을 대화 기록에 추가
        messages.append(
            {
                "role": "user",
                "content": q
            }
        )
        # 12-4. 질문 보내고 답변 받기
        try:
            answer = ask(messages)
        except Exception as e:
            # groq, gemini 둘 다 실패하면 이번 질문만 취소하고 계속 진행
            print(colored(f"답변을 가져오지 못했어요: {e}", "red"))
            messages.pop()
            continue
        # 12-5. 'RECORD:' 줄 저장하고 본문만 출력
        text = save_records(answer)
        print(colored(f"메이트 : {text}", "cyan"))
        # 12-6. AI 답도 기록에 추가
        messages.append(
            {
                "role": "assistant",
                "content": text
            }
        )


# 다른 파일(web.py)에서 import해도 대화가 시작되지 않도록 직접 실행할 때만 main() 호출
if __name__ == "__main__":
    main()
