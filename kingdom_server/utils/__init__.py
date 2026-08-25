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

def get_log_path() -> Path:
    """Return the log file path (%LocalAppData%\\KingdomAIServer\\server.log)."""
    return get_base_dir() / "server.log"
