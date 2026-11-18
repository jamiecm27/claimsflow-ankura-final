import pytest
from encrypted_backup import encrypt_archive, decrypt_archive_bytes
from backup import make_backup

def test_encryption_roundtrip(tmp_path):
    source = tmp_path/'data'; source.mkdir(); (source/'claim.json').write_text('private claim')
    plain = make_backup(source, tmp_path/'staging')
    target = encrypt_archive(plain, tmp_path/'encrypted'/'backup.cf9', 'a-long-test-passphrase')
    assert b'private claim' not in target.read_bytes()
    assert decrypt_archive_bytes(target, 'a-long-test-passphrase').startswith(b'PK')
    with pytest.raises(Exception):
        decrypt_archive_bytes(target, 'wrong-passphrase-long')
    tampered = bytearray(target.read_bytes()); tampered[-1] ^= 1; target.write_bytes(tampered)
    with pytest.raises(Exception):
        decrypt_archive_bytes(target, 'a-long-test-passphrase')

def test_no_overwrite(tmp_path):
    source = tmp_path/'data'; source.mkdir(); (source/'a').write_text('x')
    plain = make_backup(source, tmp_path/'staging')
    target = tmp_path/'a.cf9'; target.write_text('existing')
    with pytest.raises(FileExistsError):
        encrypt_archive(plain, target, 'a-long-test-passphrase')
