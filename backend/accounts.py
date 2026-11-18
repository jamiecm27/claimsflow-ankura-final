"""Standalone v9 credential store foundation. Not wired into HTTP endpoints yet.

Passwords use scrypt with per-user random salt. No initial passwords or
credentials are embedded in source. Account database must be access-restricted.
"""
import hashlib
import hmac
import os
import sqlite3
from pathlib import Path


def initialize(path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL, active INTEGER NOT NULL DEFAULT 1)')
        cols = {r[1] for r in db.execute('PRAGMA table_info(users)')}
        if 'role' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'analyst'")
    if os.name == 'posix':
        path.chmod(0o600)


def add_user(path: Path, username: str, password: str, role: str = "analyst"):
    if role not in ("admin", "analyst"):
        raise ValueError("Invalid role")
    if not username or len(username) > 80 or not username.replace('_', '').replace('-', '').isalnum():
        raise ValueError('Invalid username')
    if len(password) < 12:
        raise ValueError('Password must be at least 12 characters')
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1)
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO users(username,salt,password_hash,role) VALUES(?,?,?,?)', (username, salt, digest, role))


def verify_user(path: Path, username: str, password: str) -> bool:
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT salt,password_hash,active FROM users WHERE username=?', (username,)).fetchone()
    if not row or not row[2]:
        return False
    digest = hashlib.scrypt(password.encode('utf-8'), salt=row[0], n=2**14, r=8, p=1)
    return hmac.compare_digest(digest, row[1])


def get_role(path: Path, username: str):
    """Return the role for an active account, otherwise None."""
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT role FROM users WHERE username=? AND active=1', (username,)).fetchone()
    return row[0] if row and row[0] in ('admin', 'analyst') else None

def set_role(path: Path, username: str, role: str):
    """CLI/provisioning helper; never expose as unauthenticated HTTP endpoint."""
    if role not in ('admin', 'analyst'):
        raise ValueError('Invalid role')
    with sqlite3.connect(path) as db:
        if role != 'admin':
            current = db.execute("SELECT role,active FROM users WHERE username=?", (username,)).fetchone()
            admins = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
            if current and current[0] == 'admin' and current[1] and admins <= 1:
                raise ValueError('Cannot demote the last active admin')
        result = db.execute('UPDATE users SET role=? WHERE username=?', (role, username))
        if not result.rowcount:
            raise ValueError('Unknown user')


def set_password(path: Path, username: str, password: str):
    if len(password) < 12:
        raise ValueError('Password must be at least 12 characters')
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1)
    with sqlite3.connect(path) as db:
        result = db.execute('UPDATE users SET salt=?, password_hash=? WHERE username=? AND active=1', (salt, digest, username))
        if result.rowcount != 1:
            raise ValueError('Unknown or inactive user')

def list_users(path: Path):
    with sqlite3.connect(path) as db:
        return [{'username': u, 'role': r} for u,r in db.execute('SELECT username,role FROM users WHERE active=1 ORDER BY username')]


def session_identity(path: Path, username: str):
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT password_hash FROM users WHERE username=? AND active=1', (username,)).fetchone()
    return bytes(row[0]).hex() if row else None
