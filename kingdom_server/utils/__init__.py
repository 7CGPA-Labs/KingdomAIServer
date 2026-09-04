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
