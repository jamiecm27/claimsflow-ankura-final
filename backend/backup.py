"""Offline-safe, read-only backup of ClaimsFlow persistent data.

Run with the server stopped for a consistent multi-file snapshot. This tool
never modifies the source directory and does not restore over live data.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile


def make_backup(data_dir: Path, output_dir: Path) -> Path:
    data_dir = Path(data_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    if not data_dir.is_dir():
        raise FileNotFoundError(f'Data directory not found: {data_dir}')
    if output_dir == data_dir or data_dir in output_dir.parents:
        raise ValueError('Backup destination must be outside the data directory')
    files = sorted(p for p in data_dir.rglob('*') if p.is_file() and not p.is_symlink())
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target = output_dir / f'claimsflow-backup-{stamp}.zip'
    if target.exists():
        raise FileExistsError(f'Backup already exists: {target}')
    manifest = {'format': 'claimsflow-backup-v1', 'created_utc': datetime.now(timezone.utc).isoformat(), 'files': {}}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for path in files:
            rel = path.relative_to(data_dir).as_posix()
            blob = path.read_bytes()
            manifest['files'][rel] = {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}
            z.writestr('data/' + rel, blob)
        z.writestr('manifest.json', json.dumps(manifest, indent=2))
    verify_backup(target)
    return target


def verify_backup(archive: Path) -> dict:
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('format') != 'claimsflow-backup-v1':
            raise ValueError('Unsupported backup format')
        expected = {'manifest.json'} | {'data/' + rel for rel in manifest['files']}
        if set(z.namelist()) != expected:
            raise ValueError('Backup contents do not match manifest')
        for rel, details in manifest['files'].items():
            path = Path(rel)
            if path.is_absolute() or '..' in path.parts or '\\' in rel:
                raise ValueError('Unsafe backup filename')
            blob = z.read('data/' + rel)
            if len(blob) != details['bytes'] or hashlib.sha256(blob).hexdigest() != details['sha256']:
                raise ValueError(f'Backup integrity check failed: {rel}')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ClaimsFlow offline backup and verification')
    parser.add_argument('--data-dir', type=Path, default=Path.home()/'Library/Application Support/ClaimsFlow/data')
    parser.add_argument('--output-dir', type=Path, default=Path.home()/'Documents/ClaimsFlow Backups')
    parser.add_argument('--verify', type=Path, help='Verify an existing archive instead of creating one')
    args = parser.parse_args()
    if args.verify:
        info = verify_backup(args.verify)
        print(f"Verified {len(info['files'])} files")
    else:
        print(make_backup(args.data_dir, args.output_dir))
