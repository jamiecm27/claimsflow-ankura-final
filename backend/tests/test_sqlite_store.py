import json
import pytest
from sqlite_store import SQLiteStore, migrate_json_to_sqlite


def test_migrate_preserves_all_fields(tmp_path):
    original = {'claims': [{'id': 'C-1', 'notes': ['one', 'two']}], 'reviews': [{'id': 1}], 'custom': {'x': True}}
    source = tmp_path / 'state.json'
    source.write_text(json.dumps(original))
    dest = tmp_path / 'state.sqlite3'
    migrate_json_to_sqlite(source, dest)
    assert SQLiteStore(dest).read() == original
    assert json.loads(source.read_text()) == original
    with pytest.raises(FileExistsError):
        migrate_json_to_sqlite(source, dest)


def test_update_and_rollback(tmp_path):
    store = SQLiteStore(tmp_path / 'state.sqlite3')
    store.save({'claims': [], 'reviews': []})
    assert store.update(lambda data: data['claims'].append({'id': 'C-2'})) is None
    assert store.read()['claims'] == [{'id': 'C-2'}]
    def broken(data):
        data['claims'].append({'id': 'BAD'})
        raise RuntimeError('fail')
    with pytest.raises(RuntimeError):
        store.update(broken)
    assert store.read()['claims'] == [{'id': 'C-2'}]


def test_invalid_source_rejected(tmp_path):
    src = tmp_path / 'bad.json'
    src.write_text('{"claims": []}')
    dest = tmp_path / 'new.sqlite3'
    with pytest.raises(ValueError):
        migrate_json_to_sqlite(src, dest)
    assert not dest.exists()
