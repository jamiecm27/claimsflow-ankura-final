"""Shared Gemini credential stored in the current macOS login Keychain.

Other trusted local Python applications can use get_gemini_key().
No secrets are written to the project folder.
"""
import os
import sys

SERVICE = "uk.claimsflow.shared-ai.gemini"
ACCOUNT = "default"


def get_gemini_key():
    if sys.platform == "darwin":
        try:
            import keyring
            return (keyring.get_password(SERVICE, ACCOUNT) or "").strip()
        except Exception:
            return ""
    return (os.environ.get("GEMINI_API_KEY") or "").strip()


def save_gemini_key(value):
    if sys.platform != "darwin":
        raise RuntimeError("Keychain setup requires macOS")
    import keyring
    keyring.set_password(SERVICE, ACCOUNT, value)
    if keyring.get_password(SERVICE, ACCOUNT) != value:
        raise RuntimeError("Could not verify Keychain save")
