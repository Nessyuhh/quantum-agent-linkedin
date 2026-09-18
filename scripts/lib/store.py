"""La file de contenus. Un seul fichier JSON versionne dans le repo."""
import json, os, tempfile, uuid
from datetime import datetime, timezone
from .config import QUEUE

EMPTY = {"state": {"telegram_offset": 0}, "ideas": [], "items": []}

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def load() -> dict:
    if not QUEUE.exists():
        return json.loads(json.dumps(EMPTY))
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    for k, v in EMPTY.items():
        data.setdefault(k, json.loads(json.dumps(v)))
    return data

def save(data: dict) -> None:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(QUEUE.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, QUEUE)

def find(data: dict, item_id: str):
    return next((i for i in data["items"] if i["id"] == item_id), None)

def pending_ideas(data: dict, limit: int):
    fresh = [i for i in data["ideas"] if not i.get("used")]
    fresh.sort(key=lambda i: (i.get("source") != "terrain", i.get("created_at", "")))
    return fresh[:limit]

def recent_subjects(data: dict, days: int = 60):
    from datetime import timedelta
    cut = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [i.get("angle", "") for i in data["items"] if i.get("created_at", "") >= cut]
