import json
import sqlite3
import pytest
from storage_config import create_store
from sqlite_store import migrate_json_to_sqlite
from sqlite_snapshot import snapshot_database


def test_json_remains_default(tmp_path):
    store = create_store(tmp_path)
    assert (tmp_path / 'claimsflow.json').exists()
    assert store.read()['claims']


def test_sqlite_refuses_unmigrated_json(tmp_path):
    create_store(tmp_path, 'json')
    with pytest.raises(RuntimeError, match='migration'):
        create_store(tmp_path, 'sqlite')


def test_migrated_sqlite_preserves_claims(tmp_path):
    original = create_store(tmp_path, 'json').read()
    migrate_json_to_sqlite(tmp_path / 'claimsflow.json', tmp_path / 'claimsflow.sqlite3')
    assert create_store(tmp_path, 'sqlite').read() == original


def test_sqlite_snapshot_includes_committed_wal_updates(tmp_path):
    store = create_store(tmp_path, 'sqlite')
    store.update(lambda d: d['reviews'].append({'id': 'review-one'}))
    result = snapshot_database(tmp_path / 'claimsflow.sqlite3', tmp_path / 'backups' / 'snapshot.sqlite3')
    with sqlite3.connect(result) as db:
        data = json.loads(db.execute('select payload from state where id=1').fetchone()[0])
    assert data['reviews'] == [{'id': 'review-one'}]
    with pytest.raises(FileExistsError):
        snapshot_database(tmp_path / 'claimsflow.sqlite3', result)


def test_unknown_backend_rejected(tmp_path):
    with pytest.raises(ValueError):
        create_store(tmp_path, 'bogus')
