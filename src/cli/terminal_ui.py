"""
Kingdom AI Server - Rich Terminal CLI (Direct Inline Code Architecture).
Interacts with LLM engine, 2-Minister Council, and hardware telemetry via direct Python calls.
No HTTP REST endpoints are used - all communication is in-process.
"""
import sys
import time
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.theme import Theme
except ImportError:
    print("[ERROR] 'rich' package is required. Install with: pip install rich")
    sys.exit(1)

from src.core.local_llm import LlamaCppOrchestrator
from src.core.hardware import HardwareManager, STATIC_VRAM_CEILING_MB
from src.processing.cache import ResponseCacheDB
from src.prompts.templates import HeuristicIntentRouter
from src.rag.embedder import BGEEmbedder
from src.rag.retriever import BGEReranker

# Custom Rich theme
kingdom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "header": "bold magenta",
    "metric": "bold cyan",
})

console = Console(theme=kingdom_theme)


class KingdomCLI:
    """Direct inline code terminal interface for Kingdom AI Server."""

    def __init__(self):
        self.orchestrator = LlamaCppOrchestrator()
        self.hw_manager = HardwareManager()
        
        # Hardwire VRAM registration so telemetry accurately reflects loaded constraints
        # Main Boss (1100), Minister 1 (35), Minister 2 (110)
        self.hw_manager.register_allocation(1100)
        self.hw_manager.register_allocation(35)
        self.hw_manager.register_allocation(110)
        
        self.cache_db = ResponseCacheDB()
        self.router = HeuristicIntentRouter()
        self.embedder = BGEEmbedder()
        self.reranker = BGEReranker()
        self.chat_history = []
        self.total_cache_hits = 0
        self.total_queries = 0

    def display_banner(self):
        """Display startup banner with system diagnostics."""
        diag = self.hw_manager.detect_environment()

        banner_text = Text()
        banner_text.append("👑 KINGDOM AI SERVER CLI\n", style="bold magenta")
        banner_text.append(f"   Engine: llama.cpp Vulkan/OpenCL (GGUF)\n", style="info")
        banner_text.append(f"   VRAM Ceiling: {STATIC_VRAM_CEILING_MB} MB\n", style="info")
        banner_text.append(f"   GPU Provider: {diag['selected_provider']}\n", style="info")
        banner_text.append(f"   System RAM: {diag['available_ram_gb']} GB available / {diag['system_ram_gb']} GB total\n", style="info")
        banner_text.append(f"   CPU Cores: {diag['cpu_cores']}\n", style="info")
        banner_text.append(f"   Model Loaded: {self.orchestrator.is_loaded}\n", style="success" if self.orchestrator.is_loaded else "warning")

        console.print(Panel(banner_text, title="[bold]System Diagnostics[/bold]", border_style="cyan"))
        console.print()
        console.print("[dim]Commands: /top (htop monitor)  /health  /cache  /clearcache  /index <path>  /clearindex  /audit  /clear  /quit[/dim]")
        console.print("[dim]Type your message and press Enter to chat.[/dim]")
        console.print()

    def show_health(self):
        """Display hardware telemetry via direct inline code."""
        diag = self.hw_manager.detect_environment()
        cache_stats = self.cache_db.get_stats()

        table = Table(title="🔍 Health & Telemetry", border_style="cyan")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="metric")

        table.add_row("GPU Provider", diag["selected_provider"])
        table.add_row("VRAM Ceiling", f"{STATIC_VRAM_CEILING_MB} MB")
        table.add_row("VRAM Allocated", f"{self.hw_manager.vram_allocated_mb} MB")
        table.add_row("System RAM", f"{diag['available_ram_gb']} GB / {diag['system_ram_gb']} GB")
        table.add_row("CPU Cores", str(diag["cpu_cores"]))
        table.add_row("Model Loaded", "✅ Yes" if self.orchestrator.is_loaded else "❌ No")
        table.add_row("Cache Entries", str(cache_stats.get("total_entries", 0)))
        table.add_row("Cache Hit Ratio", f"{cache_stats.get('hit_ratio_pct', 0):.1f}%")
        table.add_row("Session Queries", str(self.total_queries))
        table.add_row("Session Cache Hits", str(self.total_cache_hits))

        console.print(table)

    def show_cache_stats(self):
        """Display detailed cache statistics via direct inline code."""
        stats = self.cache_db.get_stats()

        table = Table(title="📦 Response Cache Statistics", border_style="green")
        table.add_column("Metric", style="bold")
        table.add_column("Value", style="metric")

        for key, value in stats.items():
            table.add_row(str(key), str(value))

        console.print(table)

    def show_top_monitor(self):
        """Open full-screen interactive K-Top (htop-style) live system monitor."""
        from rich.live import Live
        from src.cli.server_dashboard import KingdomTopDashboard
        from src.inference.inference_engine import LOCAL_BEARER_TOKEN

        dashboard = KingdomTopDashboard(
            host="127.0.0.1",
            port=58420,
            bearer_token=LOCAL_BEARER_TOKEN
        )
        dashboard.attach_engines(cache_db=self.cache_db, orchestrator=self.orchestrator)
        dashboard.status_message = "● IN-PROCESS (Direct Python Session)"

        try:
            with Live(dashboard.build_layout(), console=console, screen=True, refresh_per_second=3) as live:
                while True:
                    time.sleep(0.3)
                    if sys.platform == "win32":
                        try:
                            import msvcrt
                            if msvcrt.kbhit():
                                ch = msvcrt.getch()
                                if ch in (b'\x00', b'\xe0'):
                                    msvcrt.getch()
                                    continue
                                key = ch.decode("utf-8", errors="ignore").lower()
                                if key in ("q", "\x1b"):  # 'q' or ESC
                                    break
                                elif key == "c":
                                    self.cache_db.clear()
                                    dashboard.status_message = "● CACHE CLEARED"
                                elif key == "h":
                                    dashboard.show_help = not dashboard.show_help
                                elif key == "r":
                                    dashboard.status_message = "● FORCED REFRESH"
                        except Exception:
                            pass
                    else:
                        break
                    live.update(dashboard.build_layout())
        except (KeyboardInterrupt, Exception):
            pass

    def process_chat(self, user_input: str) -> Optional[str]:
        """Process a chat message through the full inline pipeline."""
        self.total_queries += 1

        # Step 1: Cache hit check (< 0.05 ms)
        msgs = self.chat_history + [{"role": "user", "content": user_input}]
        import json
        prompt_summary = json.dumps(msgs)
        cache_key = ResponseCacheDB.compute_cache_key("qwen2.5-coder-1.5b", prompt_summary, "", 0.7, 512)

        cached = self.cache_db.get(cache_key)
        if cached:
            self.total_cache_hits += 1
            # Extract text from cached response
            if isinstance(cached, dict):
                choices = cached.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", str(cached))
            return str(cached)

        # Step 2: Route intent (< 0.05 ms)
        route_info = self.router.route_intent(user_input)

        # Step 3: RAG enrichment if needed (embedding + reranking)
        context_chunks = []
        if route_info["target_agent"] == "MINISTER_1_2_RAG":
            try:
                from src.rag.vector_store import VectorStore
                query_vec = self.embedder.embed_query(user_input)
                vs = VectorStore()
                candidates = vs.search_similar(query_vec, top_k=5)
                if candidates:
                    context_chunks = self.reranker.rerank(user_input, candidates, top_k=3)
            except Exception:
                pass

        # Step 4: Build enriched prompt and generate
        enriched_msgs = list(msgs)
        if context_chunks:
            context_text = "\n".join(c.get("content", "") for c in context_chunks)
            enriched_msgs.insert(0, {"role": "system", "content": f"Relevant workspace context:\n{context_text}"})

        prompt = self.orchestrator.format_chat_prompt(enriched_msgs)
        result = self.orchestrator.generate_completion(prompt, max_tokens=512, temperature=0.7)

        response_text = result.get("text", "")

        # Step 5: Cache the response (only if it's a real response, not a placeholder)
        if "uninitialized - placeholder" not in response_text:
            created_time = int(time.time())
            response_data = {
                "id": f"chatcmpl-{created_time}",
                "object": "chat.completion",
                "created": created_time,
                "model": "qwen2.5-coder-1.5b",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": response_text}, "finish_reason": "stop"}],
                "usage": result.get("usage", {})
            }
            self.cache_db.put(cache_key, response_text, response_data, query_type="CHAT")

        # Update chat history
        self.chat_history.append({"role": "user", "content": user_input})
        self.chat_history.append({"role": "assistant", "content": response_text})

        return response_text

    def display_response(self, text: str, elapsed_ms: float):
        """Display assistant response with telemetry."""
        # Render response as markdown
        console.print(Panel(Markdown(text), title="[bold green]👑 Assistant[/bold green]", border_style="green"))

        # Telemetry bar
        telemetry = Text()
        telemetry.append(f"  ⏱ {elapsed_ms:.1f}ms", style="dim cyan")
        telemetry.append(f"  |  📦 Cache Hits: {self.total_cache_hits}/{self.total_queries}", style="dim")
        telemetry.append(f"  |  🧠 VRAM: {self.hw_manager.vram_allocated_mb}/{STATIC_VRAM_CEILING_MB} MB", style="dim")
        console.print(telemetry)
        console.print()

    def run(self):
        """Main interactive REPL loop."""
        self.display_banner()

        while True:
            try:
                user_input = console.input("[bold cyan]You >[/bold cyan] ").strip()

                if not user_input:
                    continue

                # Command handling
                if user_input.lower() in ("/quit", "/exit", "/q"):
                    console.print("[dim]Goodbye! 👋[/dim]")
                    break
                elif user_input.lower() in ("/top", "/htop", "/monitor"):
                    self.show_top_monitor()
                    continue
                elif user_input.lower() == "/health":
                    self.show_health()
                    continue
                elif user_input.lower() == "/cache":
                    self.show_cache_stats()
                    continue
                elif user_input.lower() == "/clearcache":
                    self.cache_db.clear()
                    self.total_cache_hits = 0
                    console.print("[success]Cache database cleared successfully.[/success]")
                    continue
                elif user_input.lower().startswith("/index "):
                    target_path = user_input[7:].strip()
                    self.index_workspace(target_path)
                    continue
                elif user_input.lower() == "/clearindex":
                    from src.rag.vector_store import VectorStore
                    vs = VectorStore()
                    vs.clear_vault()
                    console.print("[success]Vector Store (RAG memory) cleared successfully.[/success]")
                    continue
                elif user_input.lower() == "/audit":
                    self.audit_workspace()
                    continue
                elif user_input.lower() == "/clear":
                    self.chat_history.clear()
                    console.clear()
                    self.display_banner()
                    console.print("[success]Chat history cleared.[/success]")
                    continue

                # Process chat with spinner
                start_time = time.perf_counter()
                with console.status("[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
                    response = self.process_chat(user_input)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                if response:
                    self.display_response(response, elapsed_ms)
                else:
                    console.print("[warning]No response generated.[/warning]")

            except KeyboardInterrupt:
                console.print("\n[dim]Interrupted. Type /quit to exit.[/dim]")
            except EOFError:
                break
            except Exception as e:
                console.print(f"[error]Error: {e}[/error]")

    def index_workspace(self, target_path: str):
        """Index a local directory into the SQLite vector database."""
        from pathlib import Path
        path = Path(target_path).resolve()
        if not path.exists() or not path.is_dir():
            console.print(f"[error]Invalid directory path: {path}[/error]")
            return

        console.print(f"[info]Indexing workspace: {path}[/info]")
        from src.processing.chunking import TreeSitterChunker
        from src.rag.vector_store import VectorStore
        chunker = TreeSitterChunker()
        vs = VectorStore()

        # Ensure embedder is loaded
        if not self.embedder.is_model_loaded:
            with console.status("Loading Minister 1 (Embedder)..."):
                self.embedder._load_session()

        valid_exts = {".py", ".js", ".ts", ".cpp", ".c", ".rs", ".go"}
        files_indexed = 0
        chunks_indexed = 0

        with console.status("[bold cyan]Scanning and Chunking...[/bold cyan]", spinner="dots") as status:
            for filepath in path.rglob("*"):
                if filepath.is_file() and filepath.suffix in valid_exts:
                    try:
                        content = filepath.read_text(encoding="utf-8")
                        chunks = chunker.chunk_file(content, filepath.suffix)
                        for chunk in chunks:
                            text = chunk.get("content", "")
                            if text:
                                vec = self.embedder.embed_query(text)
                                vs.insert_chunk(
                                    str(filepath), 
                                    text, 
                                    vec, 
                                    chunk.get("start_line", 1), 
                                    chunk.get("end_line", 1)
                                )
                                chunks_indexed += 1
                        files_indexed += 1
                        status.update(f"[bold cyan]Scanning... Indexed {files_indexed} files ({chunks_indexed} chunks)[/bold cyan]")
                    except Exception as e:
                        pass

        console.print(f"[success]Indexing complete! {files_indexed} files and {chunks_indexed} chunks added to Vector Store.[/success]")

    def audit_workspace(self):
        """Run VulnerabilityScanner on all chunks in the Vector Store."""
        from pathlib import Path
        from src.rag.vector_store import VectorStore
        from src.processing.preprocessor import VulnerabilityScanner
        from rich.table import Table

        vs = VectorStore()
        scanner = VulnerabilityScanner()
        chunks = vs.get_all_chunks()
        
        if not chunks:
            console.print("[warning]Vector Store is empty. Use /index <path> to index a codebase first.[/warning]")
            return
            
        console.print(f"[info]Auditing {len(chunks)} chunks in Vector Store...[/info]")
        
        all_findings = []
        with console.status("[bold cyan]Running Security Audit...[/bold cyan]", spinner="dots"):
            for chunk in chunks:
                findings = scanner.scan_security_issues(chunk["content"])
                for f in findings:
                    f["file_path"] = chunk["file_path"]
                    # Add chunk line offset
                    f["actual_line"] = f["line_number"] + chunk["line_start"] - 1
                    all_findings.append(f)
                    
        if not all_findings:
            console.print("[success]Audit complete! 0 vulnerabilities found.[/success]")
            return
            
        table = Table(title="Security Audit Findings")
        table.add_column("Severity", style="bold red")
        table.add_column("File", style="cyan")
        table.add_column("Line", style="yellow")
        table.add_column("Description", style="white")
        
        for f in sorted(all_findings, key=lambda x: (x["severity"], x["file_path"])):
            severity_label = f["severity"].upper()
            color = "red" if severity_label == "CRITICAL" or severity_label == "HIGH" else "yellow"
            table.add_row(
                f"[{color}]{severity_label}[/{color}]",
                Path(f["file_path"]).name,
                str(f["actual_line"]),
                f["description"]
            )
            
        console.print(table)
        console.print(f"[warning]Found {len(all_findings)} potential security issues.[/warning]")


def main():
    """Entry point for the Kingdom CLI."""
    cli = KingdomCLI()
    cli.run()


if __name__ == "__main__":
    main()
