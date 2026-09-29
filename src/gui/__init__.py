"""
Kingdom AI Studio V3 - GUI Controller & Native Slint Integration Layer.
Direct in-process bindings connecting Slint UI events to Kingdom AI's LLM engine.
"""

from src.gui.app_controller import AppController
from src.gui.telemetry_bridge import TelemetryBridge
from src.gui.worker import InferenceWorker, DownloadWorker
from src.gui.models_adapter import (
    STUDIO_MODELS_CATALOG,
    get_model_spec,
    get_model_filepath,
    build_slint_model_list
)

__all__ = [
    "AppController",
    "TelemetryBridge",
    "InferenceWorker",
    "DownloadWorker",
    "STUDIO_MODELS_CATALOG",
    "get_model_spec",
    "get_model_filepath",
    "build_slint_model_list"
]
