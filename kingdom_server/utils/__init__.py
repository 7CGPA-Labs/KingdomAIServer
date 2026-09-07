"""
Utility modules for model verification, telemetry, and environment paths.
"""
import os
from pathlib import Path

def get_base_dir() -> Path:
    """Return the user-space root directory for KingdomAIServer (%LocalAppData%\\KingdomAIServer)."""
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    base_dir = Path(local_app_data) / "KingdomAIServer"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

def get_models_dir() -> Path:
    """Return the models directory (%LocalAppData%\\KingdomAIServer\\models)."""
    models_dir = get_base_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir

def get_db_path() -> Path:
    """Return the SQLite database vault path (%LocalAppData%\\KingdomAIServer\\vault.db)."""
    return get_base_dir() / "vault.db"

def get_logs_dir() -> Path:
    """Return the logs directory (%LocalAppData%\\KingdomAIServer\\logs)."""
    local_logs = Path("logs")
    parent_logs = Path("..") / "logs"
    if local_logs.exists() and local_logs.is_dir():
        return local_logs.resolve()
    elif parent_logs.exists() and parent_logs.is_dir():
        return parent_logs.resolve()

    logs_dir = get_base_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir

def get_log_path() -> Path:
    """Return the log file path (%LocalAppData%\\KingdomAIServer\\logs\\server.log)."""
    return get_logs_dir() / "server.log"

import shutil

def get_roles_dir() -> Path:
    """Return the prompt roles directory (%LocalAppData%\\KingdomAIServer\\roles), auto-provisioning defaults."""
    roles_dir = get_base_dir() / "roles"
    roles_dir.mkdir(parents=True, exist_ok=True)
    
    bundled_roles_dir = Path(__file__).parent.parent / "roles"
    if bundled_roles_dir.exists():
        for role_file in bundled_roles_dir.glob("*.txt"):
            target_file = roles_dir / role_file.name
            if not target_file.exists():
                try:
                    shutil.copy2(role_file, target_file)
                except Exception:
                    pass
    return roles_dir

def load_role_prompt(role_name: str) -> str:
    """Load prompt role text for a given minister or boss (e.g., 'main_boss', 'minister_1')."""
    roles_dir = get_roles_dir()
    role_file = roles_dir / f"{role_name}.txt"
    if role_file.exists():
        try:
            return role_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    bundled_file = Path(__file__).parent.parent / "roles" / f"{role_name}.txt"
    if bundled_file.exists():
        try:
            return bundled_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    return f"Role for {role_name} active."

