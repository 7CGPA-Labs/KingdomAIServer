"""
FastAPI Server Gateway Adapter for Kingdom AI Server.
Forwards imports to src.inference.inference_engine for V2 backward compatibility.
"""
from src.inference.inference_engine import app

__all__ = ["app"]
