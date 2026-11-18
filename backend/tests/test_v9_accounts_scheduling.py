import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accounts import initialize, add_user, verify_user
from scheduled_backup import run_backup
from backup import verify_backup


def test_two_accounts(tmp_path):
    db = tmp_path/'accounts.sqlite3'
    initialize(db)
    add_user(db, 'operator', 'strong-test-passphrase-one')
    add_user(db, 'analyst', 'strong-test-passphrase-two')
    assert verify_user(db, 'operator', 'strong-test-passphrase-one')
    assert verify_user(db, 'analyst', 'strong-test-passphrase-two')
    assert not verify_user(db, 'analyst', 'strong-test-passphrase-one')
    assert not verify_user(db, 'unknown', 'strong-test-passphrase-two')


def test_password_policy_and_duplicate(tmp_path):
    db = tmp_path/'accounts.sqlite3'
    initialize(db)
    with pytest.raises(ValueError):
        add_user(db, 'analyst', 'short')
    add_user(db, 'analyst', 'long-enough-password')
    with pytest.raises(Exception):
        add_user(db, 'analyst', 'another-long-password')


def test_backup_retention(tmp_path):
    data = tmp_path/'live'; data.mkdir()
    (data/'claims.json').write_text('{}')
    out = tmp_path/'backups'
    first = run_backup(data, out, retain=1)
    # Existing timestamped backup must not be overwritten.
    with pytest.raises(FileExistsError):
        run_backup(data, out, retain=1)
    assert verify_backup(first)['files']['claims.json']['bytes'] == 2


def test_invalid_retention(tmp_path):
    with pytest.raises(ValueError):
        run_backup(tmp_path/'missing', tmp_path/'backups', retain=0)
