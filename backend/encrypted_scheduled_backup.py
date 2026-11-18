"""One-shot encrypted backup for use with launchd; JSON data must be quiescent."""
import argparse
import os
import tempfile
from pathlib import Path
from backup import make_backup
from encrypted_backup import encrypt_archive, decrypt_archive_bytes

def run(data_dir, output_dir, password, retain=14):
    if retain < 1:
        raise ValueError('Retention must be positive')
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Plaintext archive exists only in a temporary, owner-only directory.
    with tempfile.TemporaryDirectory(prefix='claimsflow-staging-') as staging:
        plain = make_backup(Path(data_dir), Path(staging))
        target = output_dir / (plain.stem + '.cf9')
        encrypt_archive(plain, target, password)
        decrypt_archive_bytes(target, password)
    candidates = sorted(output_dir.glob('claimsflow-backup-*.cf9'))
    for old in candidates[:-retain]:
        old.unlink()
    return target

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--data-dir', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--retain', type=int, default=14)
    a = p.parse_args()
    password = os.environ.get('CLAIMSFLOW_BACKUP_PASSWORD')
    if not password:
        p.error('CLAIMSFLOW_BACKUP_PASSWORD is required; do not put it in a launchd plist')
    print(run(a.data_dir, a.output_dir, password, a.retain))
