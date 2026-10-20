"""프로필과 활동 기록을 JSON 파일로 저장한다."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PROFILE_FILE = DATA_DIR / "profile.json"
LOG_FILE = DATA_DIR / "log.json"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path: Path, data) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile() -> dict:
    return _read(PROFILE_FILE, {"job": "", "certs": "", "studying": ""})


def save_profile(profile: dict) -> None:
    _write(PROFILE_FILE, profile)


def load_log() -> list[dict]:
    return _read(LOG_FILE, [])


def add_record(record: dict) -> None:
    log = load_log()
    record["saved_at"] = datetime.now().isoformat(timespec="seconds")
    record.setdefault("date", date.today().isoformat())
    log.append(record)
    _write(LOG_FILE, log)


def recent_log(days: int = 7) -> list[dict]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    return [r for r in load_log() if r.get("date", "") >= since]
