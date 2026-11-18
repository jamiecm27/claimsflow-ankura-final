"""Consistent SQLite backup using sqlite3's online backup API (safe with WAL)."""
from pathlib import Path
import sqlite3


def snapshot_database(source: Path, destination: Path) -> Path:
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Exclusive reservation prevents overwriting a prior backup.
        with destination.open('xb'):
            pass
        with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as src, sqlite3.connect(destination) as dst:
            src.backup(dst)
        with sqlite3.connect(destination) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite backup integrity check failed')
        return destination
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
