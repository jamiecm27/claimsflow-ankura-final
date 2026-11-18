"""Opt-in, single-run backup job for an external scheduler.

Only use on a quiescent JSON data directory; SQLite online snapshots are a
separate operation. Never installs a scheduler or modifies the running server.
"""
import argparse
from pathlib import Path
from backup import make_backup, verify_backup


def run_backup(data_dir: Path, output_dir: Path, retain: int = 14) -> Path:
    if retain < 1:
        raise ValueError('retain must be at least 1')
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result = make_backup(data_dir, output_dir)
    verify_backup(result)
    # Only prune verified, recognised backups; never touch arbitrary files.
    candidates = sorted(output_dir.glob('claimsflow-backup-*.zip'))
    verified = []
    for path in candidates:
        try:
            verify_backup(path)
        except Exception:
            continue
        verified.append(path)
    for path in verified[:-retain]:
        if path != result:
            path.unlink()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='One-shot backup job (requires quiescent JSON data)')
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--retain', type=int, default=14)
    args = parser.parse_args()
    print(run_backup(args.data_dir, args.output_dir, args.retain))
