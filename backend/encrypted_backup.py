"""Password-encrypted, authenticated backup envelope; no plaintext archive on disk."""
import argparse
import io
import os
import json
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from backup import verify_backup

MAGIC = b'CF9ENC1\n'

def _key(password, salt):
    if len(password) < 16:
        raise ValueError('Backup passphrase must be at least 16 characters')
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())

def encrypt_archive(archive: Path, destination: Path, password: str):
    archive, destination = Path(archive), Path(destination)
    verify_backup(archive)
    if destination.exists():
        raise FileExistsError(destination)
    salt, nonce = os.urandom(16), os.urandom(12)
    ciphertext = AESGCM(_key(password, salt)).encrypt(nonce, archive.read_bytes(), MAGIC)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(MAGIC + salt + nonce + ciphertext)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination

def decrypt_archive_bytes(encrypted: Path, password: str):
    blob = Path(encrypted).read_bytes()
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + 16 + 12 + 16:
        raise ValueError('Not a ClaimsFlow encrypted backup')
    pos = len(MAGIC)
    raw = AESGCM(_key(password, blob[pos:pos+16])).decrypt(blob[pos+16:pos+28], blob[pos+28:], MAGIC)
    # Validate integrity without creating plaintext files.
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('format') != 'claimsflow-backup-v1':
            raise ValueError('Invalid backup manifest')
        import hashlib
        expected = {'manifest.json'} | {'data/' + p for p in manifest['files']}
        if set(z.namelist()) != expected:
            raise ValueError('Backup file mismatch')
        for name, meta in manifest['files'].items():
            p = Path(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name:
                raise ValueError('Unsafe backup entry')
            content = z.read('data/' + name)
            if len(content) != meta['bytes'] or hashlib.sha256(content).hexdigest() != meta['sha256']:
                raise ValueError('Backup integrity mismatch')
    return raw

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('encrypted_output', type=Path)
    parser.add_argument('--password-env', default='CLAIMSFLOW_BACKUP_PASSWORD')
    args = parser.parse_args()
    secret = os.environ.get(args.password_env)
    if not secret:
        parser.error('Backup password environment variable is missing')
    print(encrypt_archive(args.archive, args.encrypted_output, secret))
