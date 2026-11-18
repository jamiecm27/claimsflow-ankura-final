import sys
from pathlib import Path
import zipfile
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backup import make_backup, verify_backup


def test_backup_and_verify(tmp_path):
    data = tmp_path/'live'; (data/'evidence'/'CLM-001').mkdir(parents=True)
    (data/'workbench_v7.json').write_text('{"claims": []}')
    (data/'evidence'/'CLM-001'/'a.pdf').write_bytes(b'%PDF-test')
    result = make_backup(data, tmp_path/'backups')
    manifest = verify_backup(result)
    assert len(manifest['files']) == 2
    assert (data/'workbench_v7.json').read_text() == '{"claims": []}'


def test_backup_refuses_nested_destination(tmp_path):
    data = tmp_path/'live'; data.mkdir()
    with pytest.raises(ValueError):
        make_backup(data, data/'backups')


def test_tampering_detected(tmp_path):
    data = tmp_path/'live'; data.mkdir(); (data/'a.json').write_text('original')
    archive = make_backup(data, tmp_path/'backups')
    with zipfile.ZipFile(archive, 'a') as z:
        z.writestr('data/a.json', b'tampered')
    with pytest.raises(ValueError):
        verify_backup(archive)
