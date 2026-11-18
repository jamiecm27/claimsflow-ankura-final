"""Opt-in SQLite persistence for v9. Does not modify the v8 JSON store.

The existing Store.read/save/update interface is retained. SQLite transactions
serialize writes across processes; WAL permits concurrent readers.
"""
import json
import sqlite3
from pathlib import Path
from threading import RLock
from core import sample_claims


class SQLiteStore:
    def __init__(self, path: Path, seed=True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            if seed:
                db.execute('INSERT OR IGNORE INTO state (id, payload) VALUES (1, ?)',
                           (json.dumps({'claims': sample_claims(), 'reviews': []}),))

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=30000')
        return db

    def read(self):
        with self.lock, self._connect() as db:
            row = db.execute('SELECT payload FROM state WHERE id=1').fetchone()
            if row is None:
                raise ValueError('SQLite store is uninitialised')
            return json.loads(row[0])

    def save(self, data):
        payload = json.dumps(data)
        with self.lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO state(id,payload) VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (payload,))
            db.commit()

    def update(self, fn):
        with self.lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM state WHERE id=1').fetchone()
            if row is None:
                raise ValueError('SQLite store is uninitialised')
            data = json.loads(row[0])
            try:
                result = fn(data)
                db.execute('UPDATE state SET payload=? WHERE id=1', (json.dumps(data),))
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise


def migrate_json_to_sqlite(json_path: Path, sqlite_path: Path):
    """One-time, non-destructive migration; refuses to overwrite a database."""
    json_path = Path(json_path)
    sqlite_path = Path(sqlite_path)
    if not json_path.is_file():
        raise FileNotFoundError(json_path)
    data = json.loads(json_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('claims'), list) or not isinstance(data.get('reviews'), list):
        raise ValueError('Invalid ClaimsFlow JSON structure')
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        raise FileExistsError(sqlite_path)
    # Exclusive creation avoids accidentally replacing a live database.
    with sqlite_path.open('xb'):
        pass
    try:
        store = SQLiteStore(sqlite_path, seed=False)
        store.save(data)
        if store.read() != data:
            raise ValueError('Migration verification failed')
    except BaseException:
        sqlite_path.unlink(missing_ok=True)
        raise
    return sqlite_path


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Non-destructive ClaimsFlow JSON to SQLite migration')
    p.add_argument('source_json', type=Path)
    p.add_argument('destination_sqlite', type=Path)
    a = p.parse_args()
    print(migrate_json_to_sqlite(a.source_json, a.destination_sqlite))
