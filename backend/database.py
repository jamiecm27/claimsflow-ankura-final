import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "claims.json"

_db_lock = Lock()


def _default_database():
    return {"claims": []}


def _ensure_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        _write_database(_default_database())


def _read_database():
    _ensure_database()

    with DB_PATH.open("r", encoding="utf-8") as database_file:
        return json.load(database_file)


def _write_database(data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = DB_PATH.with_suffix(".tmp")

    with temp_path.open("w", encoding="utf-8") as database_file:
        json.dump(data, database_file, indent=2)
        database_file.write("\n")

    os.replace(temp_path, DB_PATH)


def get_claims():
    with _db_lock:
        data = _read_database()
        return data.get("claims", [])


def add_claim(claim_data):
    with _db_lock:
        data = _read_database()
        claims = data.setdefault("claims", [])

        claim = {
            "id": uuid4().hex,
            "processedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **claim_data,
        }

        claims.insert(0, claim)
        _write_database(data)

        return claim


def clear_claims():
    with _db_lock:
        _write_database(_default_database())
