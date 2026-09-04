# 👑 Kingdom AI Server & Open WebUI

[![Build & Package](https://github.com/7CGPA-Labs/KingdomAIServer/actions/workflows/build.yml/badge.svg)](https://github.com/7CGPA-Labs/KingdomAIServer/actions/workflows/build.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows Enterprise](https://img.shields.io/badge/platform-Windows%20x64-0078D6.svg)](https://microsoft.com/windows)
[![Port: 58420](https://img.shields.io/badge/port-127.0.0.1%3A58420-success.svg)](http://127.0.0.1:58420)

**Kingdom AI Server** is a zero-admin, enterprise-secure local **OpenAI-Compatible AI Server & Open WebUI** for [Continue.dev](https://continue.dev) and local desktop AI development.

It features a **Lightweight Browser-Based Open WebUI** served directly over `http://127.0.0.1:58420`. The entire backend relies on a **100% ONNX DirectML Acceleration Engine**, running the Senior Boss model (`Qwen2.5-Coder-1.5B-Instruct`) via **`onnxruntime-genai-directml`** and the 8-Minister Council via **`onnxruntime-directml`**.

---

## 🏛️ System Architecture

```mermaid
graph TD
    User[Developer Browser UI / Continue.dev] -->|HTTP / SSE Port 58420| Server[FastAPI Server]
    Server -->|DirectML Acceleration Chain| Engine[Dual DirectML Engine]
    Engine -->|onnxruntime-genai-directml| Boss[Senior Boss LLM: Qwen2.5-Coder 1.5B ONNX]
    Engine -->|onnxruntime-directml| Ministers[8-Minister ONNX Council]
    Server -->|Vector Search| Vault[SQLite MemoryVault]

    subgraph 8-Minister Council
        Ministers --> M1[Minister 1: Intent Router]
        Ministers --> M2[Minister 2: Repo Embedder]
        Ministers --> M3[Minister 3: Re-Ranker]
        Ministers --> M4[Minister 4: Code Parser]
        Ministers --> M5[Minister 5: Speed Autocomplete]
        Ministers --> M6[Minister 6: Fact Checker]
        Ministers --> M7[Minister 7: Security Auditor]
        Ministers --> M8[Minister 8: Asset & Diagram Gen]
    end
```

---

## ⚡ Dual DirectML Hardware Acceleration Engine

| Model Subsystem | Artifact Format | Primary Acceleration Provider | Target Silicon |
| :--- | :--- | :--- | :--- |
| **Senior Boss LLM** | `Qwen2.5-Coder-1.5B-ONNX` (INT4 ONNX GenAI) | **`onnxruntime-genai-directml`** | Intel Iris Xe / Arc / AMD / NVIDIA |
| **8-Minister Council** | 8 ONNX Models (~1.2 GB ONNX) | **`onnxruntime-directml`** (DirectX 12 Compute EUs) | DirectX 12 GPU / OpenVINO NPU |

---

## 🚀 Quick Start & Single-Line Installation

Run the non-admin installer script in PowerShell:

```powershell
irm https://raw.githubusercontent.com/7CGPA-Labs/KingdomAIServer/main/Deploy-KingdomServer.ps1 | iex
```

### Launch Server & Open WebUI:

Start the server using pure Python:

```bash
python main.py
```
*Or alternatively:*
```bash
python start_server.py
```

*Your default browser will automatically open to `http://127.0.0.1:58420` displaying the Kingdom AI Open WebUI.*

---

## 🔌 Continue.dev VS Code Integration Guide

Add the following configuration to your `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "Kingdom AI Server (Qwen2.5-Coder)",
      "provider": "openai",
      "model": "qwen2.5-coder-1.5b",
      "apiBase": "http://127.0.0.1:58420/v1",
      "apiKey": "EMPTY"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Kingdom Autocomplete (Granite 128M)",
    "provider": "openai",
    "model": "granite-code-128m",
    "apiBase": "http://127.0.0.1:58420/v1",
    "apiKey": "EMPTY"
  }
}
```

---

## 🧪 Verification & Testing

Run the automated unit test suite:

```powershell
.\venv\Scripts\python.exe -m pytest -v
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
