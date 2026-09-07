"""
Enterprise Security Authentication & Local Token Management.
Auto-generates and validates 256-bit cryptographically secure hex bearer token stored in %LocalAppData%\\KingdomAIServer\\.token
"""
import os
import secrets
from pathlib import Path
from typing import Optional
from kingdom_server.utils import get_base_dir

_TOKEN_FILE = get_base_dir() / ".token"

def get_or_create_auth_token() -> str:
    """Returns the persistent 256-bit authentication token, generating one if missing."""
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _TOKEN_FILE.exists() and _TOKEN_FILE.stat().st_size > 0:
        try:
            token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
            if len(token) >= 32:
                return token
        except Exception:
            pass

    new_token = secrets.token_hex(32)
    try:
        _TOKEN_FILE.write_text(new_token, encoding="utf-8")
        if hasattr(os, "chmod"):
            try:
                os.chmod(_TOKEN_FILE, 0o600)
            except Exception:
                pass
    except Exception:
        pass
    return new_token

def validate_bearer_token(provided_token: Optional[str]) -> bool:
    """Validates if the provided token matches the local bearer secret."""
    if not provided_token:
        return False
    expected_token = get_or_create_auth_token()
    if provided_token.startswith("Bearer "):
        provided_token = provided_token[7:].strip()
    return secrets.compare_digest(provided_token.strip(), expected_token)
