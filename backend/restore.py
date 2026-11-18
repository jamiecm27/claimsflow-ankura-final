"""Offline restore into a NEW directory only. Never overwrites live data."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from backup import verify_backup

MAX_FILES = 10000
MAX_BYTES = 2 * 1024 * 1024 * 1024


def restore_to_new_directory(archive: Path, destination: Path) -> dict:
    archive = Path(archive).expanduser().resolve(strict=True)
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'Restore destination already exists: {destination}')
    if not destination.parent.is_dir():
        raise FileNotFoundError('Restore destination parent does not exist')
    if destination.parent.is_symlink():
        raise ValueError('Restore destination parent cannot be a symlink')
    manifest = verify_backup(archive)
    entries = manifest['files']
    if len(entries) > MAX_FILES or sum(v['bytes'] for v in entries.values()) > MAX_BYTES:
        raise ValueError('Backup exceeds restore safety limits')
    staging = Path(tempfile.mkdtemp(prefix='.claimsflow-restore-', dir=destination.parent))
    try:
        with zipfile.ZipFile(archive) as z:
            for rel in entries:
                parts = Path(rel).parts
                if not parts or any(part in ('', '.', '..') for part in parts) or rel.startswith('/'):
                    raise ValueError('Unsafe filename in archive')
                target = staging.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open('data/' + rel) as source, target.open('xb') as out:
                    shutil.copyfileobj(source, out)
        # A rename in the same parent directory publishes the complete restore.
        if destination.exists() or destination.is_symlink():
            raise FileExistsError('Restore destination appeared during restore')
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Restore a ClaimsFlow backup to a NEW folder; never replaces live data')
    parser.add_argument('archive', type=Path)
    parser.add_argument('new_directory', type=Path)
    args = parser.parse_args()
    info = restore_to_new_directory(args.archive, args.new_directory)
    print(f"Restored {len(info['files'])} files into {args.new_directory}")
