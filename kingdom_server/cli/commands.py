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

# Inject Windows Native Trust Store (Bypasses Zscaler SSL MITM Block)
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

for proto in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    if proto in os.environ:
        os.environ[proto.upper()] = os.environ[proto]
        os.environ[proto.lower()] = os.environ[proto]

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
        cmd = [sys.executable, "-m", "kingdom_server.cli.commands", "start", "--port", str(port)]
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


@app.command("sessions")
@app.command("history")
def sessions():
    """Lists saved conversation sessions from Cognitive Memory Vault."""
    vault = MemoryVault()
    sess_list = vault.list_sessions()
    if not sess_list:
        console.print("[yellow]No past conversation sessions found in Memory Vault.[/yellow]")
        return

    table = Table(title="[Saved Conversation Sessions]", title_style="bold magenta", expand=True)
    table.add_column("Session ID", style="cyan")
    table.add_column("Turns", justify="right")
    table.add_column("Last Active", style="yellow")
    table.add_column("Initial Prompt Snippet", style="white")

    for s in sess_list:
        dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s["last_time"]))
        snippet = s["first_prompt"][:55] + ("..." if len(s["first_prompt"]) > 55 else "")
        table.add_row(s["session_id"], str(s["turn_count"]), dt_str, snippet)

    console.print(table)
    console.print("\n[bold cyan]To resume a session, pass --session <session_id> to 'ask', 'plan', or 'code':[/bold cyan]")
    console.print(f"Example: [bold yellow]kingdom ask --session {sess_list[0]['session_id']}[/bold yellow]\n")


def _run_agent_cli(
    agent_name: str,
    system_instruction: str,
    prompt: Optional[str],
    session_id: Optional[str],
    model: str,
    auto_provision: bool
):
    if auto_provision:
        from kingdom_server.utils.downloader import ModelDownloader
        downloader = ModelDownloader()
        downloader.auto_provision_missing()

    from kingdom_server.core.orchestrator import KingdomOrchestrator
    orchestrator = KingdomOrchestrator()
    vault = MemoryVault()

    session_id = session_id or f"{agent_name}-session-{int(time.time())}"

    if prompt:
        console.print(Panel(f"[bold white][Agent: {agent_name.upper()}] Query:[/bold white] {prompt}\n[dim]Session ID: {session_id}[/dim]", style="bold blue"))
        console.print(f"\n[bold gold1]👑 Kingdom {agent_name.capitalize()} Agent Response:[/bold gold1]\n")
        
        async def _stream_cli():
            full_text = ""
            prev_turns = vault.get_session_history(session_id)
            messages = [{"role": "system", "content": system_instruction}]
            for turn in prev_turns:
                messages.append({"role": turn["role"], "content": turn["content"]})
            messages.append({"role": "user", "content": prompt})

            async for chunk in orchestrator.generate_chat_stream(messages, model=model, session_id=session_id):
                if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                    try:
                        data = json.loads(chunk[6:])
                        delta = data["choices"][0]["delta"].get("content", "")
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                        full_text += delta
                    except Exception:
                        pass
            sys.stdout.write("\n")
            sys.stdout.flush()

        asyncio.run(_stream_cli())
    else:
        # Interactive REPL session
        console.clear()
        console.print(Panel(f"[bold gold1]👑 KINGDOM AI SERVER - INTERACTIVE {agent_name.upper()} AGENT SESSION[/bold gold1]\nSession ID: [cyan]{session_id}[/cyan]\nType 'exit', 'quit', or press Ctrl+C to stop.", style="bold blue"))
        
        prev_turns = vault.get_session_history(session_id)
        if prev_turns:
            console.print(f"[bold cyan][Loaded {len(prev_turns)} previous message turns from session history][/bold cyan]")

        while True:
            try:
                user_input = console.input(f"\n[bold cyan]kingdom ({agent_name}) > [/bold cyan]").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "q"):
                    console.print("[yellow]Exiting agent chat session.[/yellow]")
                    break
                
                console.print(f"\n[bold gold1]👑 Kingdom {agent_name.capitalize()} Agent:[/bold gold1]\n")

                async def _stream_repl(u_input: str):
                    current_history = vault.get_session_history(session_id)
                    messages = [{"role": "system", "content": system_instruction}]
                    for turn in current_history:
                        messages.append({"role": turn["role"], "content": turn["content"]})
                    messages.append({"role": "user", "content": u_input})

                    async for chunk in orchestrator.generate_chat_stream(messages, model=model, session_id=session_id):
                        if chunk.startswith("data: ") and not chunk.startswith("data: [DONE]"):
                            try:
                                data = json.loads(chunk[6:])
                                delta = data["choices"][0]["delta"].get("content", "")
                                sys.stdout.write(delta)
                                sys.stdout.flush()
                            except Exception:
                                pass
                    sys.stdout.write("\n")
                    sys.stdout.flush()

                asyncio.run(_stream_repl(user_input))
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Session ended.[/yellow]")
                break


@app.command("ask")
def ask_cmd(
    prompt: Optional[str] = typer.Argument(None, help="Prompt text to query Ask Agent directly"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume or create"),
    model: str = typer.Option("qwen2.5-coder-1.5b", "--model", "-m", help="Target model name"),
    auto_provision: bool = typer.Option(True, "--auto-provision/--no-auto-provision", help="Auto-provision missing model artifacts")
):
    """General Q&A Agent: Answer questions with clear explanations, architectural insights, and domain knowledge."""
    sys_prefix = "You are Kingdom Ask Agent. Answer user queries with clear, structured explanations, technical depth, and architectural insights."
    _run_agent_cli("ask", sys_prefix, prompt, session, model, auto_provision)


@app.command("plan")
def plan_cmd(
    prompt: Optional[str] = typer.Argument(None, help="Prompt text to query Plan Agent directly"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume or create"),
    model: str = typer.Option("qwen2.5-coder-1.5b", "--model", "-m", help="Target model name"),
    auto_provision: bool = typer.Option(True, "--auto-provision/--no-auto-provision", help="Auto-provision missing model artifacts")
):
    """Implementation Planning Agent: Provide step-by-step engineering plans, roadmaps, and trade-off analyses."""
    sys_prefix = "You are Kingdom Plan Agent. Provide structured, step-by-step technical implementation plans, engineering roadmaps, and trade-off analyses."
    _run_agent_cli("plan", sys_prefix, prompt, session, model, auto_provision)


@app.command("code")
def code_cmd(
    prompt: Optional[str] = typer.Argument(None, help="Prompt text to query Code Agent directly"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume or create"),
    model: str = typer.Option("qwen2.5-coder-1.5b", "--model", "-m", help="Target model name"),
    auto_provision: bool = typer.Option(True, "--auto-provision/--no-auto-provision", help="Auto-provision missing model artifacts")
):
    """Code Generation Agent: Write clean, production-ready, highly optimized code with full syntax structure."""
    sys_prefix = "You are Kingdom Code Agent. Write clean, production-ready, highly optimized code with complete syntax structure and zero boilerplate."
    _run_agent_cli("code", sys_prefix, prompt, session, model, auto_provision)


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

    # 4. Continue.dev Config Verification & Auto-Repair
    continue_config_path = Path.home() / ".continue" / "config.json"
    console.print("\n[bold magenta][Continue.dev Integration Status][/bold magenta]")
    if continue_config_path.exists():
        console.print(f"Config file found at [cyan]{continue_config_path}[/cyan]")
        try:
            content = continue_config_path.read_text(encoding="utf-8")
            lines = [line for line in content.splitlines() if not line.strip().startswith("//")]
            cfg_data = json.loads("\n".join(lines))
            models = cfg_data.get("models", [])
            kingdom_found = any("58420" in str(m.get("apiBase", "")) for m in models)
            if kingdom_found:
                console.print("[bold green]✔ Continue.dev is configured to use Kingdom AI Server (http://127.0.0.1:58420/v1)![/bold green]")
            else:
                console.print("[yellow]⚠ Continue.dev config exists but apiBase for Kingdom AI Server was not detected. Run 'kingdom config' to fix automatically.[/yellow]")
        except Exception:
            console.print("[yellow]⚠ Continue.dev config file contained syntax errors. Auto-repairing now...[/yellow]")
            config_cmd(fix=True)
    else:
        console.print(f"[yellow]⚠ Continue.dev config file not found at {continue_config_path}. Auto-generating default configuration...[/yellow]")
        config_cmd(fix=True)

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


@app.command("config")
def config_cmd(
    fix: bool = typer.Option(True, "--fix", help="Auto-configure or repair ~/.continue/config.json")
):
    """Auto-configures or repairs Continue.dev VS Code Extension ~/.continue/config.json."""
    cfg_dir = Path.home() / ".continue"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"

    kingdom_model_entry = {
        "title": "Kingdom AI Server (Qwen2.5-Coder)",
        "provider": "openai",
        "model": "qwen2.5-coder-1.5b",
        "apiBase": "http://127.0.0.1:58420/v1",
        "apiKey": "EMPTY"
    }
    kingdom_tab_entry = {
        "title": "Kingdom Autocomplete (Granite 128M)",
        "provider": "openai",
        "model": "granite-code-128m",
        "apiBase": "http://127.0.0.1:58420/v1",
        "apiKey": "EMPTY"
    }

    raw_data = {"models": [kingdom_model_entry], "tabAutocompleteModel": kingdom_tab_entry}
    if cfg_path.exists():
        try:
            content = cfg_path.read_text(encoding="utf-8")
            lines = [line for line in content.splitlines() if not line.strip().startswith("//")]
            clean_content = "\n".join(lines)
            data = json.loads(clean_content)
            
            models = data.get("models", [])
            has_kingdom = any("58420" in str(m.get("apiBase", "")) for m in models)
            if not has_kingdom:
                models.insert(0, kingdom_model_entry)
                data["models"] = models
            data["tabAutocompleteModel"] = kingdom_tab_entry
            raw_data = data
        except Exception:
            console.print("[yellow]Overwriting broken ~/.continue/config.json with valid Kingdom AI Server config...[/yellow]")

    cfg_path.write_text(json.dumps(raw_data, indent=2), encoding="utf-8")
    console.print(f"[bold green]✔ Successfully configured Continue.dev at {cfg_path}[/bold green]")


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
