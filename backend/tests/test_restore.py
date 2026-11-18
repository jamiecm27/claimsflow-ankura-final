import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backup import make_backup
from restore import restore_to_new_directory


def test_restore_round_trip(tmp_path):
    data = tmp_path/'data'; (data/'evidence').mkdir(parents=True)
    (data/'claimsflow.json').write_text('{"claims": []}')
    (data/'evidence'/'proof.pdf').write_bytes(b'%PDF-1.4')
    archive = make_backup(data, tmp_path/'backups')
    restore_to_new_directory(archive, tmp_path/'restored')
    assert (tmp_path/'restored'/'claimsflow.json').read_bytes() == (data/'claimsflow.json').read_bytes()
    assert (tmp_path/'restored'/'evidence'/'proof.pdf').read_bytes() == b'%PDF-1.4'


def test_restore_never_overwrites(tmp_path):
    data = tmp_path/'data'; data.mkdir(); (data/'a').write_text('original')
    archive = make_backup(data, tmp_path/'backups')
    dest = tmp_path/'existing'; dest.mkdir(); (dest/'a').write_text('keep')
    with pytest.raises(FileExistsError):
        restore_to_new_directory(archive, dest)
    assert (dest/'a').read_text() == 'keep'


def test_restore_rejects_corrupt_archive(tmp_path):
    data = tmp_path/'data'; data.mkdir(); (data/'a').write_text('original')
    archive = make_backup(data, tmp_path/'backups')
    archive.write_bytes(b'corrupt')
    with pytest.raises(Exception):
        restore_to_new_directory(archive, tmp_path/'restored')
    assert not (tmp_path/'restored').exists()
