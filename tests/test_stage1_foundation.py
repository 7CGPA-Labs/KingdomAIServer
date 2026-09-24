"""
Unit tests for Stage 1 Foundation & Directory Architecture setup.
"""
import pytest
import os
from src.config import get_model_config, get_logging_config
from src.core.hardware import HardwareManager, STATIC_VRAM_CEILING_MB
from src.processing.preprocessor import Preprocessor
# from src.processing.tokenizer import format_fim_prompt (DISABLED: FIM Autocomplete)

def test_stage1_config_loader():
    model_cfg = get_model_config()
    assert "server" in model_cfg
    assert model_cfg["server"]["port"] == 58420
    assert "hardware" in model_cfg
    assert model_cfg["hardware"]["max_static_vram_mb"] == 1250

def test_hardware_vram_ceiling():
    hw = HardwareManager()
    assert hw.verify_vram_budget(1100) is True
    assert hw.verify_vram_budget(375) is True
    with pytest.raises(MemoryError):
        hw.verify_vram_budget(4000)

def test_regex_security_scanner():
    prep = Preprocessor()
    dirty_code = "api_key = 'sk_live_1234567890abcdef12345'\nos.system('rm -rf /')"
    findings = prep.scan_security_issues(dirty_code)
    assert len(findings) >= 1

# FIM Autocomplete test (DISABLED)
# def test_fim_prompt_formatter():
#     formatted = format_fim_prompt("def add(a, b):", "return a + b")
#     assert "<|fim_prefix|>" in formatted
#     assert "<|fim_suffix|>" in formatted
#     assert "<|fim_middle|>" in formatted
