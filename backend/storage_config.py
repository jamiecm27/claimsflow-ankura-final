"""Explicit opt-in storage selection. JSON remains the default for v8 compatibility."""
import os
from pathlib import Path
from store import Store
from sqlite_store import SQLiteStore


def create_store(data_dir: Path, backend=None):
    data_dir = Path(data_dir)
    choice = (backend if backend is not None else os.environ.get('CLAIMSFLOW_STORAGE_BACKEND', 'json')).strip().lower()
    if choice == 'json':
        return Store(data_dir / 'claimsflow.json')
    if choice == 'sqlite':
        path = data_dir / 'claimsflow.sqlite3'
        # Fail closed rather than creating a seeded database that hides existing JSON data.
        if not path.exists() and (data_dir / 'claimsflow.json').exists():
            raise RuntimeError('JSON data exists but SQLite migration is missing. Run the offline migration first.')
        return SQLiteStore(path)
    raise ValueError('CLAIMSFLOW_STORAGE_BACKEND must be json or sqlite')
