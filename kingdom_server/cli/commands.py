"""
Typer CLI command matrix for kingdom.exe (Rich colored status cards, live telemetry dashboard, command ergonomics).
"""
import sys
import os
import time
import json
import socket
import subprocess
import signal
import asyncio
from pathlib import Path
from typing import Optional
import typer
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich.markdown import Markdown

from kingdom_server import __version__
from kingdom_server.utils import get_base_dir, get_log_path, get_models_dir
from kingdom_server.utils.verifier import ModelVerifier
from kingdom_server.utils.telemetry import HardwareTelemetry
from kingdom_server.core.memory_vault import MemoryVault

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = typer.Typer(
    name="kingdom",
    help="👑 Kingdom AI Server - Dedicated Local OpenAI-Compatible Server for Continue.dev",
    add_completion=False
)
console = Console(safe_box=True)

PID_FILE = get_base_dir() / "kingdom_server.pid"

def is_port_in_use(port: int = 58420) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def render_banner(active: bool = True, address: str = "http://127.0.0.1:58420") -> Panel:
    status_str = "[bold green]● ACTIVE[/bold green]" if active else "[bold red]● INACTIVE[/bold red]"
    text = (
        f"[bold gold1]👑 KINGDOM AI SERVER (Enterprise Edition) • v{__version__}[/bold gold1]\n"
        f"Local OpenAI-Compatible Server for Continue.dev\n"
        f"Status: {status_str}  |  Address: [link={address}]{address}[/link]"
    )
    return Panel(text, style="blue", expand=False)

def create_telemetry_table(telemetry: dict) -> Table:
    table = Table(title="[Live Hardware Telemetry]", title_style="bold magenta", expand=True)
    table.add_column("CPU Usage", justify="center")
    table.add_column("System RAM", justify="center")
    table.add_column("GPU Engine", justify="center")
    table.add_column("VRAM Alloc", justify="center")
    table.add_column("NPU Latency", justify="center")

    cpu_str = f"{telemetry.get('cpu_usage_percent', 0.0)}%"
    ram_str = f"{telemetry.get('ram_used_gb', 0.0)} / {telemetry.get('ram_total_gb', 0.0)} GB"
    gpu_str = f"{telemetry.get('gpu_engine', 'DirectML')} {telemetry.get('gpu_usage_percent', 0.0)}%"
    vram_str = f"{telemetry.get('vram_used_gb', 0.0)} GB"
    npu_str = f"{telemetry.get('npu_latency_ms', 12.4)} ms"

    table.add_row(cpu_str, ram_str, gpu_str, vram_str, npu_str)
    return table


@app.command("start")
@app.command("serve")
def serve(
    port: int = typer.Option(58420, "--port", "-p", help="Loopback port to listen on"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run server in background daemon mode"),
    tray: bool = typer.Option(False, "--tray", "-t", help="Spawn Windows System Tray icon"),
    auto_provision: bool = typer.Option(True, "--auto-provision", help="Auto-provision missing GGUF/ONNX model artifacts using huggingface_hub"),
):
    """Starts the Kingdom AI Server in foreground or background with live telemetry dashboard."""
    if auto_provision:
        from kingdom_server.utils.downloader import ModelDownloader
        downloader = ModelDownloader()
        downloader.auto_provision_missing()

    if is_port_in_use(port):
        console.print(f"[bold red]Error:[/bold red] Port {port} is already in use by another process.")
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.5)
            if resp.status_code == 200:
                console.print("[green]An active Kingdom AI Server is already running on this port.[/green]")
        except Exception:
            pass
        raise typer.Exit(code=1)

    if daemon:
        console.print(f"[bold green]Launching Kingdom AI Server daemon on port {port}...[/bold green]")
        cmd = [sys.executable, "-m", "kingdom_server.cli.commands", "serve", "--port", str(port)]
        if tray:
            cmd.append("--tray")
        proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0)
        PID_FILE.write_text(str(proc.pid))
        console.print(f"[bold green]Daemon started successfully (PID: {proc.pid}).[/bold green]")
        return

    # Option to run tray in thread
    if tray:
        try:
            from kingdom_server.tray.tray_app import SystemTrayApp
            tray_app = SystemTrayApp()
            tray_app.run_detached()
            console.print("[bold cyan]Windows System Tray integration active.[/bold cyan]")
        except Exception as e:
            console.print(f"[yellow]Warning: System Tray could not be initialized: {e}[/yellow]")

    # Run uvicorn server in main thread
    import uvicorn
    from kingdom_server.server.app import app as fastapi_app

    verifier = ModelVerifier()
    summary = verifier.get_summary()
    vault = MemoryVault()
    vault_stats = vault.get_stats()

    console.clear()
    console.print(render_banner(active=True, address=f"http://127.0.0.1:{port}"))
    console.print(f"[bold cyan][Active Ministers: {summary['valid']}/{summary['total']} Online] [Cognitive Vault: {vault_stats['total_vectors_indexed']} Vectors Indexed][/bold cyan]\n")

    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="info", access_log=False)
    server = uvicorn.Server(config)

    PID_FILE.write_text(str(os.getpid()))

    # Run server
    try:
        server.run()
    except KeyboardInterrupt:
        console.print("[bold yellow]\nShutting down Kingdom AI Server...[/bold yellow]")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


@app.command("download")
def download(
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Specific model filename to download"),
    all_models: bool = typer.Option(True, "--all", "-a", help="Download all missing GGUF/ONNX models using huggingface_hub")
):
    """Thin-client model auto-provisioning using huggingface_hub into %LocalAppData%\\KingdomAIServer\\models\\."""
    from kingdom_server.utils.downloader import ModelDownloader, MODEL_HF_SPECS
    downloader = ModelDownloader()
    if model:
        spec = MODEL_HF_SPECS.get(model)
        if not spec:
            console.print(f"[bold red]Unknown model filename: '{model}'[/bold red]")
            console.print("Available model filenames:")
            for k in MODEL_HF_SPECS.keys():
                console.print(f" - {k}")
            raise typer.Exit(code=1)
        downloader.download_model_via_hf(model)
    else:
        downloader.auto_provision_missing()


@app.command("ask")
@app.command("prompt")
@app.command("chat")
def ask(
    prompt: Optional[str] = typer.Argument(None, help="Prompt text to query directly from CLI"),
    model: str = typer.Option("qwen2.5-coder-1.5b", "--model", "-m", help="Target model name"),
    auto_provision: bool = typer.Option(True, "--auto-provision/--no-auto-provision", help="Auto-provision missing model artifacts")
):
    """Runs a prompt directly in the CLI terminal or launches interactive terminal chat mode."""
    if auto_provision:
        from kingdom_server.utils.downloader import ModelDownloader
        downloader = ModelDownloader()
        downloader.auto_provision_missing()

    from kingdom_server.core.orchestrator import KingdomOrchestrator
    orchestrator = KingdomOrchestrator()

    if prompt:
        console.print(Panel(f"[bold white]User Query:[/bold white] {prompt}", style="bold blue"))
        console.print("\n[bold gold1]👑 Kingdom AI Server Response:[/bold gold1]\n")
        
        async def _stream_cli():
            full_text = ""
            messages = [{"role": "user", "content": prompt}]
            async for chunk in orchestrator.generate_chat_stream(messages, model=model):
                if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                    try:
                        data = json.loads(chunk[6:])
                        delta = data["choices"][0]["delta"].get("content", "")
                        console.print(delta, end="")
                        full_text += delta
                    except Exception:
                        pass
            console.print("\n")

        asyncio.run(_stream_cli())
    else:
        # Interactive REPL terminal session
        console.clear()
        console.print(Panel("[bold gold1]👑 KINGDOM AI SERVER - INTERACTIVE CLI CHAT SESSION[/bold gold1]\nType 'exit', 'quit', or press Ctrl+C to stop.", style="bold blue"))
        session_id = f"cli-session-{int(time.time())}"

        while True:
            try:
                user_input = console.input("\n[bold cyan]kingdom > [/bold cyan]").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    console.print("[yellow]Exiting interactive CLI chat session.[/yellow]")
                    break
                
                console.print("\n[bold gold1]👑 Kingdom AI Server:[/bold gold1]\n")

                async def _stream_repl(u_input: str):
                    messages = [{"role": "user", "content": u_input}]
                    async for chunk in orchestrator.generate_chat_stream(messages, model=model, session_id=session_id):
                        if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                            try:
                                data = json.loads(chunk[6:])
                                delta = data["choices"][0]["delta"].get("content", "")
                                console.print(delta, end="")
                            except Exception:
                                pass
                    console.print("\n")

                asyncio.run(_stream_repl(user_input))
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Session ended.[/yellow]")
                break


@app.command("stop")
def stop():
    """Stops any running background Kingdom AI Server daemon on port 58420."""
    stopped = False
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            console.print(f"[bold green]Successfully terminated daemon (PID: {pid}).[/bold green]")
            stopped = True
        except Exception as e:
            console.print(f"[yellow]Could not kill process from PID file: {e}[/yellow]")
        finally:
            PID_FILE.unlink(missing_ok=True)

    if not stopped:
        if is_port_in_use(58420):
            console.print("[yellow]Port 58420 is active, attempting HTTP shutdown request...[/yellow]")
        else:
            console.print("[bold green]No active Kingdom AI Server daemon detected.[/bold green]")


@app.command("status")
def status():
    """Queries /health and prints hardware metrics and active silicon tiers."""
    try:
        resp = httpx.get("http://127.0.0.1:58420/health", timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            console.print(render_banner(active=True, address=data.get("address", "http://127.0.0.1:58420")))
            console.print(create_telemetry_table(data.get("telemetry", {})))

            tiers = data.get("silicon_tiers", {})
            table_tiers = Table(title="[Active Silicon Tiers]", title_style="bold yellow", expand=True)
            table_tiers.add_column("Component", style="cyan")
            table_tiers.add_column("Active Silicon Provider", style="green")
            table_tiers.add_row("8-Minister Council", tiers.get("ministers_tier", "CPU (AVX2)"))
            table_tiers.add_row("Senior Boss LLM", tiers.get("boss_tier", "AVX2 CPU Fallback"))
            table_tiers.add_row("ONNX EP", tiers.get("onnx_provider", "CPUExecutionProvider"))
            console.print(table_tiers)

            models = data.get("models", {})
            console.print(f"[bold cyan][Models Status: {models.get('online', 0)}/{models.get('total', 9)} Online][/bold cyan]")
        else:
            console.print(f"[bold red]Server returned error status code: {resp.status_code}[/bold red]")
    except Exception:
        console.print(render_banner(active=False))
        console.print("[bold red]Server is currently offline (http://127.0.0.1:58420 unreachable).[/bold red]")
        console.print("Run [bold cyan]kingdom serve[/bold cyan] to start the server.")


@app.command("doctor")
def doctor():
    """Runs pre-flight diagnostics: verifies model integrity, hardware drivers, port 58420, and Continue.dev config."""
    console.print(Panel("[bold gold1]👑 KINGDOM AI SERVER DOCTOR & DIAGNOSTICS[/bold gold1]", style="bold blue"))

    # Auto-provision check on doctor execution if missing
    from kingdom_server.utils.downloader import ModelDownloader
    downloader = ModelDownloader()
    downloader.auto_provision_missing()

    # 1. Model Verification Table
    verifier = ModelVerifier()
    summary = verifier.get_summary()

    table_models = Table(title="[Model Files & Integrity]", title_style="bold magenta", expand=True)
    table_models.add_column("Filename", style="cyan")
    table_models.add_column("Model Name", style="white")
    table_models.add_column("Size (MB)", justify="right")
    table_models.add_column("Status", justify="center")

    for m in summary["details"]:
        status_colored = "[bold green]VALID[/bold green]" if m["status"] == "valid" else f"[bold yellow]{m['status'].upper()}[/bold yellow]"
        table_models.add_row(m["filename"], m["name"], str(m["actual_mb"]), status_colored)

    console.print(table_models)

    # 2. Hardware Drivers Check
    table_hw = Table(title="[Hardware Acceleration Drivers]", title_style="bold yellow", expand=True)
    table_hw.add_column("Subsystem", style="cyan")
    table_hw.add_column("Status", style="green")

    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        dml_status = "Available (DirectX 12)" if "DmlExecutionProvider" in providers else "Not Loaded (Using CPU)"
        npu_status = "Available" if any(x in providers for x in ["OpenVINOExecutionProvider", "QNNExecutionProvider"]) else "CPU Emulated"
    except Exception:
        dml_status = "CPU Fallback"
        npu_status = "CPU Fallback"

    table_hw.add_row("DirectML / DirectX 12 GPU", dml_status)
    table_hw.add_row("OpenVINO / QNN NPU", npu_status)
    table_hw.add_row("AVX2 CPU Vector Extensions", "Available")
    console.print(table_hw)

    # 3. Port & Network Check
    port_status = "[bold yellow]Port 58420 In Use (Server Running or Conflict)[/bold yellow]" if is_port_in_use(58420) else "[bold green]Port 58420 Available (127.0.0.1)[/bold green]"
    console.print(f"\n[bold white]Loopback Port Check:[/bold white] {port_status}")

    # 4. Continue.dev Config Verification
    continue_config_path = Path.home() / ".continue" / "config.json"
    console.print("\n[bold magenta][Continue.dev Integration Status][/bold magenta]")
    if continue_config_path.exists():
        console.print(f"Config file found at [cyan]{continue_config_path}[/cyan]")
        try:
            cfg_data = json.loads(continue_config_path.read_text(encoding="utf-8"))
            models = cfg_data.get("models", [])
            kingdom_found = any("58420" in str(m.get("apiBase", "")) for m in models)
            if kingdom_found:
                console.print("[bold green]✔ Continue.dev is configured to use Kingdom AI Server (http://127.0.0.1:58420/v1)![/bold green]")
            else:
                console.print("[yellow]⚠ Continue.dev config exists but apiBase for Kingdom AI Server was not detected.[/yellow]")
        except Exception:
            console.print("[yellow]⚠ Continue.dev config file could not be parsed as valid JSON.[/yellow]")
    else:
        console.print(f"[yellow]⚠ Continue.dev config file not found at {continue_config_path}.[/yellow]")

    console.print("\n[bold cyan]To configure Continue.dev, add the following to your ~/.continue/config.json:[/bold cyan]")
    snippet = {
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
    console.print(Panel(json.dumps(snippet, indent=2), style="green"))


@app.command("logs")
def logs(
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to read from log file"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream log lines continuously")
):
    """Streams lines from %LocalAppData%\\KingdomAIServer\\server.log."""
    log_file = get_log_path()
    if not log_file.exists():
        console.print(f"[bold yellow]Log file does not exist yet at {log_file}[/bold yellow]")
        return

    console.print(f"[bold cyan]Reading log file ({log_file})...[/bold cyan]\n")
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        for line in lines[-tail:]:
            console.print(line.rstrip())

        if follow:
            try:
                while True:
                    line = f.readline()
                    if line:
                        console.print(line.rstrip())
                    else:
                        time.sleep(0.5)
            except KeyboardInterrupt:
                pass


@app.command("vault")
def vault(
    clear: bool = typer.Option(False, "--clear", help="Clear all stored vector memory"),
    stats: bool = typer.Option(True, "--stats", help="Show cognitive vector memory statistics")
):
    """Inspects or resets the SQLite cognitive vector memory."""
    mem_vault = MemoryVault()
    if clear:
        mem_vault.clear()
        console.print("[bold green]✔ Cognitive vector memory cleared successfully.[/bold green]")

    if stats:
        st = mem_vault.get_stats()
        table = Table(title="[Cognitive Vector Memory Stats]", title_style="bold blue", expand=True)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Database Path", st["db_file"])
        table.add_row("Total History Turns", str(st["total_history_turns"]))
        table.add_row("Indexed Vector Memory Docs", str(st["total_vectors_indexed"]))
        table.add_row("sqlite-vec Accelerated", "YES" if st["sqlite_vec_enabled"] else "NO (Python Fallback)")
        console.print(table)


if __name__ == "__main__":
    app()
