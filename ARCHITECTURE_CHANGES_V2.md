To eliminate hardware contention on client laptops, the 10 ministers can be partitioned by delegating deterministic tasks to native compiled libraries, folding structured analytical tasks into constrained agent prompts within the Main Boss, and reserving dedicated neural runtimes strictly for operations where neural inference is non-negotiable.

---

**Category 1: Replaceable by Few Lines of Code or Native Libraries**

These tasks involve deterministic logic, syntax trees, or exact matches that probabilistic neural networks handle inefficiently compared to compiled native utilities:

* **Minister 4: Code Parser (`codeberta-base`, ~125 MB)**

* *Replacement:* **Tree-sitter** (compiled C library with language grammar bindings).


* *Why:* AST generation, scope boundary extraction, language identification, and symbol resolution are rule-based grammar problems. Tree-sitter parses complete source files in <1 ms with <5 MB of RAM, achieving 100% precision without probabilistic syntax errors or tensor memory overhead.




* **Minister 6: Fact Checker / Hallucination Auditor (`nli-deberta-v3-small`, ~90 MB)**

* *Replacement:* **Manifest Parser & Set-Lookup Script** (~50 lines of C++/Python).
* *Why:* In code generation, "hallucinated imports" are simply modules missing from the project environment. Extracting import tokens via regex or Tree-sitter and checking them against local configuration files (`package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, or standard library manifests) is an $O(1)$ set intersection taking 0.1 ms with zero false positives.




* **Minister 9: Context Compressor / Token Pruner (`LLMLingua-2`, ~80 MB)**
* *Replacement:* **AST-Guided Structural Trimmer** (native regex and Tree-sitter).
* *Why:* Removing whitespace, comments, redundant docstrings, and truncating non-relevant function implementations down to signatures (`// ... implementation elided`) can be performed deterministically, stripping 40–60% of prompt tokens without running a secondary compression neural network.


* **Minister 1 (Partial): Intent Router (`all-MiniLM-L6-v2`, ~25 MB) [Fast-Path]**

* *Replacement:* **Prefix & Rule-Based Heuristic Matcher** (e.g., catching `@workspace`, `/fix`, `/explain`, code block selections, or git diff pipes).
* *Why:* Over 80% of developer requests feature explicit IDE intent metadata that can be dispatched immediately in 0.01 ms without tensor tokenization.



---

**Category 2: Absorbed by Qwen2.5-Coder as Role-Prompted Agents with Mathematical Constraints**

These tasks require deep semantic reasoning that smaller 100M-scale encoder models handle poorly, but which the Main Boss (`Qwen2.5-Coder-1.5B`) can evaluate effectively when bound by strict sampling grammars:

* **Minister 7: Security Auditor (`codebert-vulnerability`, ~125 MB)**

* *Implementation:* Deploy an **Internal Auditor Agent Turn** using a specialized role prompt: *"You are an automated code security checker. Analyze the following diff for CWE vulnerabilities, injection sinks, and leaked credentials."*
* *Mathematical Enforcement:* Restrict logit sampling at the C++ layer using **GBNF grammars** or JSON Schema logit masks. This mathematically prevents the LLM from emitting conversational text, forcing an exact output schema:


```json
{"is_vulnerable": false, "cwe_id": null, "risk_score": 0.0}

```


* *Why:* A 1.5B coder model reasons over multi-line dataflow and taint analysis far more reliably than a 125M sequence classifier, and GBNF sampling ensures deterministic payload parsing.


* **Minister 10: Commit Message & Docstring Generator (`CodeT5` / `SmolLM`, ~90–135 MB)**
* *Implementation:* Trigger an **Agentic Utility Persona** inside Qwen2.5-Coder with temperature set to $0.0$.
* *Mathematical Enforcement:* Enforce Conventional Commits (`feat:`, `fix:`, `chore:`) via regular expression constraints passed directly to the sampler.
* *Why:* Qwen2.5-Coder already possesses strong instruction-following capabilities for summarization; dedicating an independent model solely for commit strings wastes memory bandwidth.


* **Minister 1 (Fallback): Intent Router (Ambiguous Complex Queries)**
* *Implementation:* For prompts lacking deterministic prefixes, pass the first 64 tokens to Qwen in a classification turn restricted to outputting a single token enum (`CHAT`, `EDIT`, `SEARCH`, `COMMAND`).



---

**Category 3: Retained Neural Network Ministers (Irreplaceable Sidecars)**

These models must remain dedicated neural networks on the NPU or DirectML/CPU fallback because their operations are continuous, non-autoregressive, or latency-critical:

* **Minister 2: Repo Embedder (`bge-small-en-v1.5`, ~60 MB)**

* *Why Essential:* Translating code chunks and documentation into 384-dimensional dense semantic vector space cannot be performed by rules or regex. Using the Main Boss for embeddings is impractical because causal decoder LLMs are inefficient embedders and would exhaust the GPU KV-cache during multi-file repository indexing.




* **Minister 3: Context Re-Ranker (`bge-reranker-base`, ~110 MB)**

* *Why Essential:* Vector distance alone retrieves noisy semantic matches. Cross-attention evaluation between user queries and candidate code chunks provides essential precision scoring. Passing dozens of candidate chunks directly to Qwen would overflow its 2,048–4,096 context window and introduce unacceptable prompt-processing latency.




* **Minister 5: Speed Autocomplete (`granite-code-128m`, ~130 MB)**

* *Why Essential:* Inline ghost text completion requires sub-30ms execution per keystroke. Qwen2.5-Coder-1.5B has a higher time-to-first-token (TTFT) and is often occupied streaming multi-turn chat responses. A lightweight, dedicated causal model running on an independent thread is mandatory to keep typing responsive.




* **Minister 8: Asset & Diagram Generator (`MobileDiffusion-LCM`, ~280 MB)**

* *Why Essential (for Raster Assets):* Text-to-image synthesis requires iterative latent denoising across UNet layers. Autoregressive language models cannot generate raster PNG/JPEG bitmaps. *(Note: If visual outputs are limited strictly to Mermaid.js diagrams or raw SVG code, this minister can be eliminated entirely and absorbed by the Main Boss).*





---

**Optimization Impact**

| Dimension | Original 10-Minister Setup | Triaged Architecture (3 Neural + Native + Agents) |
| --- | --- | --- |
| **Active Neural Models** | 10 Auxiliary + 1 Main Boss | **3 Auxiliary** (`bge-small`, `bge-reranker`, `granite`) + 1 Main Boss

 |
| **Sidecar RAM / VRAM** | $\approx 960\text{ MB} - 1.2\text{ GB}$<br> | **$\approx 300\text{ MB}$** |
| **Concurrent ONNX Sessions** | 8 to 10 persistent handles

 | **3 persistent handles** |
| **Preparation Latency** | 35–60 ms (stacked inference)

 | **< 15 ms** (Tree-sitter AST + parallel BGE search)

 |
| **Driver Crash Risk (`DXGI`)** | High on shared iGPU memory

 | **Negligible** (VRAM reserved almost exclusively for Qwen)

 |

This architectural division preserves system responsiveness, eliminates memory thrashing, and ensures stable execution within the tight physical constraints of mobile and enterprise laptop hardware.

# System Architecture Document: Autonomous Enterprise On-Device AI Engine

## 1. Executive Summary & Design Principles

This document specifies the production architecture for an enterprise-grade, local, OpenAI-compatible AI backend serving **Continue.dev** (VS Code) and terminal agent workflows. The architecture unifies all neural execution under a **GGUF runtime (`llama.cpp`)**, consolidates sidecars into a **Lean 3-Minister Council**, delegates inline code completion and mechanical reasoning to the **Main Boss via FIM and agent role prompts**, and shifts deterministic tasks to **zero-VRAM native libraries**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               CONTINUE.DEV / VS CODE                                   │
│                     (Chat, Code Refactor, Inline FIM Autocomplete)                     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / SSE Loopback (127.0.0.1:58420)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     FASTAPI GATEWAY & ZERO-TRUST SECURITY PERIMETER                    │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│ • Pre-Routing CSPA & Origin Defense       │ • Sliding-Window Context Compactor         │
│ • Local Bearer Secret Verification        │ • Dual-Worker Priority Queue (FIM vs Chat) │
└─────────────────────┬─────────────────────┴──────────────────────┬─────────────────────┘
                      │                                            │
                      ▼                                            ▼
┌──────────────────────────────────────────────┐ ┌───────────────────────────────────────┐
│        DETERMINISTIC NATIVE UTILITIES        │ │        THE 3-MINISTER COUNCIL         │
├──────────────────────────────────────────────┤ ├───────────────────────────────────────┤
│ • Tree-sitter Native Parser (<1ms AST/CST)   │ │ • Minister 1: Workspace Embedder (BGE)│
│ • Static AST & Manifest Import Validator     │ │ • Minister 2: Context Re-Ranker (BGE) │
│ • RegEx & Semgrep Secret/Vulnerability Filter│ │ • Minister 3: SDXS-512 Vision Engine  │
│ • Native Mermaid.js / SVG Vector Engine      │ └───────────────────┬───────────────────┘
└──────────────────────────────────────────────┘                     │
                      │                                              │
                      └──────────────────────┬───────────────────────┘
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             MAIN BOSS (Senior Software Engineer)                       │
│                        Qwen2.5-Coder-1.5B (GGUF Q4_K_M via DirectML/CPU)               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ • Core Mode 1: High-Priority FIM Autocomplete (<|fim_prefix|>, <|fim_suffix|>)        │
│ • Core Mode 2: Multi-Turn Generative Chat, Code Refactoring & Contextual Diffing       │
│ • Agent Role A: Git Commit & Docstring Craftsman (Conventional Commits)                │
│ • Agent Role B: Diff Search/Replace Realigner (Whitespace & Fuzzy Target Alignment)    │
│ • Agent Role C: Deep Taint-Flow & Security Escalation Auditor                          │
└────────────────────────────────────────────┬───────────────────────────────────────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COGNITIVE MEMORY VAULT (SQLite + sqlite-vec)                    │
│             WAL Mode | Parameterized Virtual Tables (vec0) | Cosine Distance           │
└────────────────────────────────────────────────────────────────────────────────────────┘

```

### Core Architectural Pillars

* **Absorption of Speed Autocomplete into Main Boss:** Eliminates the dedicated autocomplete neural model (`granite-code-128m` / `Qwen2.5-Coder-0.5B`). Single-line inline tab completions (`/v1/completions`) are handled directly by the **Main Boss (`Qwen2.5-Coder-1.5B`)** via native Fill-in-the-Middle (FIM) sentinel tokens and a pre-warmed, low-latency execution worker.


* **Lean 3-Minister Council:** Neural sidecars are reduced to three non-redundant models: dense vector embedding, cross-attention context re-ranking, and ultra-fast visual asset generation.


* **SDXS-512 Visual Pipeline:** Deploys a distilled single-step ($NFE = 1$) latent diffusion UNet (319M) with a 1.2M parameter feedforward micro-decoder. This avoids the heavy 83M parameter VAE decode bottleneck, delivering raster graphics in **40–90 ms** with a compact ~230 MB footprint.


* **Zero Driver Contention (`DXGI_ERROR_DEVICE_REMOVED` Prevention):** Removing the dedicated autocomplete sidecar drops total resident neural weights (Main Boss ~1.1 GB + 3 Ministers ~375 MB) to **$\approx 1.48\text{ GB}$ total VRAM/RAM**. This maintains safe operating margins on corporate laptops with integrated GPUs (Intel Arc/Iris Xe, AMD Radeon 780M/880M), preventing Windows DirectX 12 driver evictions under OS multi-tasking.


* **Deterministic Native Offloading:** Mechanical AST extraction, dependency validation, and secret detection are executed via compiled native libraries (`tree-sitter`, static AST inspectors, and compiled regex engines), running in <3 ms with zero VRAM consumption.



---

## 2. Hardware Allocation & Memory Matrix

| Subsystem Component | Implementation Tier | Technology / Engine | Parameter Count & Format | VRAM / RAM Footprint | Inference Latency |
| --- | --- | --- | --- | --- | --- |
| **Main Boss: Generative LLM** | Generative Core | `llama.cpp` (DirectML/CPU)

 | 1.5B (`Qwen2.5-Coder-1.5B` Q4_K_M)

 | ~1.1 GB

 | 35–55 tok/s |
| **Main Boss: FIM Autocomplete** | **Agent FIM Worker** | `llama.cpp` (FIM Sentinel Mode)

 | Shared with Main Boss

 | 0 MB Additional

 | 20–35 ms

 |
| **Minister 1: Workspace Embedder** | Dense Vector Representation | `llama.cpp` (`--embedding`)

 | 33.5M (`bge-small-en-v1.5` GGUF)

 | ~35 MB

 | 4–8 ms

 |
| **Minister 2: Context Re-Ranker** | Cross-Attention Scoring | `llama.cpp` / Cross-Encoder

 | 278M (`bge-reranker-base` GGUF)

 | ~110 MB

 | 10–16 ms

 |
| **Minister 3: SDXS-512 Vision** | 1-Step Latent Diffusion | DirectML / ONNX

 | ~650M total (319M UNet + 1.2M Decoder)

 | ~230 MB (INT8)

 | 40–90 ms

 |
| **Code Structure & AST Parser** | **Native Library** | `tree-sitter` (C-ABI bindings)

 | Deterministic (Zero weights)

 | <5 MB System RAM

 | <1 ms

 |
| **Import & Manifest Checker** | **Native Library** | `ast` / `importlib` / Manifest Scanners | Deterministic (Zero weights) | <2 MB System RAM | <2 ms |
| **Secret & Injection Scanner** | **Native Library** | Compiled RegEx / Semgrep Tables | Deterministic (Zero weights) | <3 MB System RAM | <3 ms |
| **Vector Diagram Engine** | **Native Library** | SVG / Mermaid.js text generator

 | Deterministic (Zero weights)

 | <1 MB System RAM | Instant

 |
| **Role A: Commit Craftsman** | **Agent Prompt Turn** | Main Boss Prompt Pipeline

 | Shared with Main Boss

 | 0 MB Dedicated

 | Streaming

 |
| **Role B: Diff Realigner** | **Agent Prompt Turn** | Main Boss Prompt Pipeline

 | Shared with Main Boss

 | 0 MB Dedicated

 | Streaming

 |
| **Role C: Security Escalation** | **Agent Prompt Turn** | Main Boss Prompt Pipeline | Shared with Main Boss | 0 MB Dedicated | Streaming |

---

## 3. Project Directory Structure

```text
generative_ai_project/
├── config/
│   ├── model_config.yaml         # GGUF paths, SDXS-512 assets, KV-cache bounds, DirectML device IDs
│   └── logging_config.yaml       # Rotating file handlers, audit telemetry formats, and security log levels
├── data/
│   ├── cache/                    # AST syntax cache, compilation artifacts, temporary image scratchpad
│   ├── embeddings/               # Local token caches and intermediate serialized vector buffers
│   └── vectordb/                 # SQLite database file (vault.db) holding sqlite-vec virtual tables
├── src/
│   ├── core/
│   │   ├── base_llm.py           # Abstract Base Class declaring common LLM inference interfaces
│   │   ├── gpt_client.py         # Upstream optional OpenAI fallback provider
│   │   ├── claude_client.py      # Upstream optional Anthropic fallback provider
│   │   ├── local_llm.py          # llama-cpp-python GGUF orchestrator (DirectML / AVX2 CPU fallback)
│   │   └── model_factory.py      # Silicon detection and execution provider dynamic loader
│   ├── prompts/
│   │   ├── templates.py          # Structured templates (System, Chat, FIM, Git Craftsman, Diff Realigner)
│   │   └── chain.py              # Multi-step agent execution chains and GBNF grammar enforcement
│   ├── rag/
│   │   ├── embedder.py           # Minister 1 wrapper generating dense 384-dim normalized vectors
│   │   ├── retriever.py          # Hybrid keyword + dense vector query pipeline with Minister 2 re-ranking
│   │   ├── vector_store.py       # SQLite + sqlite-vec interface (vec0 virtual table operations)
│   │   └── indexer.py            # AST-aware workspace indexer with strict path-traversal jailing
│   ├── processing/
│   │   ├── chunking.py           # Tree-sitter structural AST code chunker (function/class boundaries)
│   │   ├── tokenizer.py          # Subword token encoding and FIM sentinel marker injection
│   │   └── preprocessor.py       # Deterministic static analysis, AST import linting, and secret regex scans
│   └── inference/
│       ├── inference_engine.py   # Dual-worker priority queue, FastAPI loopback server, and IPC
│       └── response_parser.py    # OpenAI SSE delta chunk streamer and structured JSON output parsers
├── docs/
│   ├── README.md                 # Architecture summary, benchmark comparisons, and command reference
│   └── SETUP.md                  # Enterprise setup guide, truststore configuration, and proxy troubleshooting
├── scripts/
│   ├── setup_env.sh              # Unix/macOS environment initialization script
│   ├── setup_env.ps1             # PowerShell non-admin Windows environment initialization script
│   ├── run_tests.sh              # Automated test runner (unit, security, and hardware diagnostics)
│   ├── build_embeddings.py       # Offline workspace indexing and vector database generation tool
│   └── cleanup.py                # Cache clearing, temp scratchpad eviction, and database compaction
├── .gitignore                    # Git exclusions (data/, cache/, models/, venv/, .token)
├── Dockerfile                    # Container definition for isolated enterprise headless execution
├── docker-compose.yml            # Multi-service stack definition
└── requirements.txt              # Pinned dependencies (llama-cpp-python, onnxruntime-directml, tree-sitter)

```

---

## 4. Subsystem Design & Technical Specifications

### 4.1. The Lean 3-Minister Council

```
                      ┌────────────────────────────────────────┐
                      │        INCOMING REQUEST DISPATCH       │
                      └───────────────────┬────────────────────┘
                                          │
                   ┌──────────────────────┼──────────────────────┐
                   │                      │                      │
                   ▼                      ▼                      ▼
          ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
          │   MINISTER 1    │    │   MINISTER 2    │    │   MINISTER 3    │
          │  Repo Embedder  │    │ Context Rerank  │    │  SDXS-512 Vision│
          ├─────────────────┤    ├─────────────────┤    ├─────────────────┤
          │ • BGE-Small     │    │ • BGE-Reranker  │    │ • 319M UNet     │
          │   GGUF          │    │   GGUF          │    │ • 1.2M Decoder  │
          │ • 384-dim Dense │    │ • Cross-encoder │    │ • NFE = 1 Step  │
          │   Embeddings    │    │ • Top-3 Chunks  │    │ • 40–90 ms      │
          │ • Vector Search │    │   to Main Boss  │    │ • Raster Output │
          └─────────────────┘    └─────────────────┘    └─────────────────┘

```

1. **Minister 1: Workspace Embedder (`bge-small-en-v1.5` GGUF)**
* **Role:** Powers `/v1/embeddings` and codebase semantic indexing.


* **Operation:** Transforms source snippets into unit-normalized 384-dimensional float tensors in 4–8 ms.


* **Storage Target:** Persisted to SQLite `sqlite-vec` virtual tables (`vec0`) for fast SIMD cosine retrieval.




2. **Minister 2: Context Re-Ranker (`bge-reranker-base` GGUF)**
* **Role:** Precision relevance gatekeeper for retrieved code context.


* **Operation:** Performs deep cross-attention over `[Query, Candidate Chunk]` pairs in 10–16 ms, outputting relevance scores from 0.0 to 1.0.


* **KV-Cache Safeguard:** Passes only the top 3 scored chunks to the Main Boss prompt, keeping context concise and preventing prompt inflation.




3. **Minister 3: High-Speed Vision Engine (`SDXS-512`)**
* **Role:** On-device generation of preview assets, web wireframes, and UI mockups.


* **Architecture:**
* **UNet:** Pruned 319M parameter architecture running in a single step ($NFE = 1$).


* **Micro-Decoder:** Replaces the standard 83M VAE with a 1.2M feedforward CNN decoder.




* **Performance:** Renders $512 \times 512$ images in **40–90 ms** with ~230 MB INT8 VRAM consumption.





---

### 4.2. Main Boss Unified Execution Core & Agent Roles

The **Main Boss (`Qwen2.5-Coder-1.5B-GGUF`)** serves as both the deep conversational engine and the inline autocomplete generator via specialized execution modes and prompt chains:

```
                               ┌───────────────────────────┐
                               │  MAIN BOSS REASONING CORE │
                               │(Qwen2.5-Coder-1.5B GGUF)  │
                               └─────────────┬─────────────┘
                                             │
      ┌──────────────────────┬───────────────┴───────────────┬──────────────────────┐
      ▼                      ▼                               ▼                      ▼
┌─────────────┐        ┌─────────────┐                 ┌─────────────┐        ┌─────────────┐
│  MODE: FIM  │        │ MODE: CHAT  │                 │   ROLE A    │        │   ROLE B    │
│ AUTOCOMPL.  │        │ & REFACTOR  │                 │ GIT/DOCSTR. │        │DIFF REALIGN │
├─────────────┤        ├─────────────┤                 ├─────────────┤        ├─────────────┤
│• Prefix /   │        │• Multi-turn │                 │• Conventional│       │• Indentation│
│  Suffix FIM │        │  Chat       │                 │  Commits    │        │  Fuzzy Match│
│• High-Pri   │        │• Streaming  │                 │• JSDoc/     │        │• Exact Line │
│  Worker     │        │  SSE Diffs  │                 │  Docstrings │        │  Reconcile  │
└─────────────┘        └─────────────┘                 └─────────────┘        └─────────────┘

```

#### Speed Autocomplete Implementation (`/v1/completions`)

Instead of running a separate model daemon, `/v1/completions` dispatches FIM prompts to the Main Boss:

* **FIM Formatting:** Synthesizes incoming code cursor context into Qwen's native token structure:

$$\text{Prompt} = \texttt{<\vert{}fim\_prefix\vert{}>} + \text{Prefix} + \texttt{<\vert{}fim\_suffix\vert{}>} + \text{Suffix} + \texttt{<\vert{}fim\_middle\vert{}>}$$


* **Low-Latency Decoding:** Constrains output generation to a maximum of 32 tokens, greedy sampling ($\text{temperature} = 0.0$), and stops evaluation immediately at line breaks (`\n`) or statement terminators.


* **Turnaround Latency:** DirectML execution delivers time-to-first-token in **20–35 ms**, satisfying IDE typing fluidity.



#### Agent Prompt Roles

* **Role A: Git Commit & Docstring Craftsman (`src/prompts/templates.py`):** Converts diffs into Conventional Commits (`feat(core): ...`) and generates standard JSDoc/Sphinx documentation blocks without dedicated auxiliary networks.


* **Role B: Diff Search/Replace Realigner (`src/prompts/chain.py`):** Validates and adjusts `<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE` blocks against target source files, resolving indentation drift and line-ending variances (CRLF/LF) before diff application.


* **Role C: Security Escalation Auditor (`src/prompts/chain.py`):** Analyzes ambiguous code patterns flagged by static linters, evaluating multi-file taint flows and emitting structured risk evaluations (`{"safe": bool, "risk_level": str}`).

---

### 4.3. Deterministic Native Utility Layer (`src/processing/`)

* **Tree-sitter Native Parser (`chunking.py`):** Compiles concrete syntax trees in <1 ms using C-ABI bindings, segmenting classes and functions at exact syntactical boundaries to avoid broken code passages.


* **Static AST & Manifest Linter (`preprocessor.py`):** Compares generated import statements against active manifests (`package.json`, `requirements.txt`, `Cargo.toml`) in <2 ms via native `ast` inspection, intercepting hallucinated dependencies.


* **Secret & Vulnerability Scanner (`preprocessor.py`):** Evaluates diffs against compiled regex rules in <3 ms to intercept exposed API keys, certificates, raw SQL string concatenations, and dangerous shell sinks (`os.system`, `eval`).
* **Vector Diagram Engine (`prompts/chain.py`):** Generates declarative Mermaid.js and clean SVG diagrams directly from the Main Boss using GBNF grammar constraints, avoiding diffusion overhead for system diagrams.



---

### 4.4. Dual-Worker Priority Queue & KV-Cache Management

Inference scheduling is managed by a **Dual-Worker Priority Queue** in `src/inference/inference_engine.py` to prevent background chat generations from stalling inline autocomplete:

```
                               ┌───────────────────────────┐
                               │  INCOMING HTTP REQUESTS   │
                               └─────────────┬─────────────┘
                                             │
                      ┌──────────────────────┴──────────────────────┐
                      ▼                                             ▼
          ┌───────────────────────┐                     ┌───────────────────────┐
          │  HIGH-PRIORITY QUEUE  │                     │ STANDARD-PRIORITY QUE │
          │  (/v1/completions)    │                     │ (/v1/chat/completions)│
          └───────────┬───────────┘                     └───────────┬───────────┘
                      │                                             │
                      ▼                                             ▼
          ┌───────────────────────┐                     ┌───────────────────────┐
          │   WORKER 1: FIM RUN   │                     │  WORKER 2: CHAT RUN   │
          │ Main Boss (FIM Mode)  │                     │ Main Boss (Chat Mode) │
          │ • Preempts / Prioritiz│                     │ • Yields SSE tokens   │
          │ • Evaluates in <35 ms │                     │ • Context-compacted   │
          └───────────────────────┘                     └───────────────────────┘

```

* **Preemptive FIM Scheduling:** Incoming autocomplete calls receive highest priority, pausing long chat generation batches momentarily to evaluate single-line completions in <35 ms.


* **Sliding-Window Compaction:** When prompt history exceeds 3,500 tokens, the compaction engine preserves the system prompt and latest user prompt while sliding-window compressing historical turns to enforce the 4,096-token KV ceiling.



---

## 5. Security Perimeter & Enterprise Governance

Workstation isolation is enforced through six security controls:

1. **Loopback-Only Binding (`127.0.0.1:58420`):** Binds strictly to Windows loopback, preventing exposure on corporate subnets and eliminating Windows Firewall permission prompts.


2. **Cross-Site Port Attack (CSPA) Defense:** Inspects and drops incoming HTTP requests carrying external browser `Origin` headers.


3. **Local Bearer Authentication:** Enforces verification against a cryptographically random token stored in `%LocalAppData%\KingdomAIServer\.token`. Continue.dev supplies this token in the `Authorization: Bearer <token>` header.


4. **Zscaler Enterprise SSL Handling:** Calls `truststore.inject_into_ssl()` before any network calls, routing corporate proxy MITM certificates through Python without disabling TLS validation.


5. **SSRF Guarded Web Crawler:** Restricts outbound documentation retrieval to HTTPS allowlisted domains (`docs.rs`, `developer.mozilla.org`, `github.com`), blocking requests targeting RFC 1918 private subnets (`10.0.0.0/8`, `192.168.0.0/16`) and cloud metadata (`169.254.169.254`).


6. **Workspace Path Jailing:** Enforces validation checks ensuring file indexing remains strictly inside the developer's project root, preventing reads against user directories (`~/.ssh`, `~/.aws`, `%AppData%`).



---

## 6. Continue.dev Configuration

Both chat and autocomplete point to the unified `qwen2.5-coder-1.5b` instance at `127.0.0.1:58420/v1` in `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "Local Qwen2.5-Coder (GGUF)",
      "provider": "openai",
      "model": "qwen2.5-coder-1.5b",
      "apiBase": "http://127.0.0.1:58420/v1",
      "apiKey": "local-token"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Local Autocomplete (FIM)",
    "provider": "openai",
    "model": "qwen2.5-coder-1.5b",
    "apiBase": "http://127.0.0.1:58420/v1",
    "apiKey": "local-token"
  },
  "embeddingsProvider": {
    "provider": "openai",
    "model": "bge-small-en-v1.5",
    "apiBase": "http://127.0.0.1:58420/v1",
    "apiKey": "local-token"
  }
}

```

---

## 7. Verification Gates & Diagnostic Test Suite

The test suite (`scripts/run_tests.sh` / `scripts/run_tests.ps1`) validates the pipeline across four operational gates:

* **Gate 1: Silicon & VRAM Budget Diagnostics**
* Verifies `llama-cpp-python` initializes against DirectML with CPU fallback support.


* Asserts static VRAM usage across all models remains **$\le 1.48\text{ GB}$**, preventing `DXGI_ERROR_DEVICE_REMOVED` allocation failures.




* **Gate 2: Deterministic Native Utility Performance**
* Asserts `tree-sitter` executes syntax parsing across Python, TypeScript, Go, and Rust in $<1\text{ ms}$.


* Confirms `preprocessor.py` catches API tokens, secrets, and invalid imports in $<5\text{ ms}$.


* **Gate 3: 3-Minister Council & FIM Latency Benchmark**
* Confirms Main Boss FIM code completion returns via `/v1/completions` in **$<35\text{ ms}$**.


* Asserts Minister 1 calculates 384-dimensional embeddings in $<8\text{ ms}$ and persists them into `sqlite-vec`.


* Asserts Minister 2 computes context re-ranking scores in $<16\text{ ms}$.


* Asserts Minister 3 renders $512 \times 512$ SDXS-512 images in **$<100\text{ ms}$**.




* **Gate 4: Protocol Compliance & Security Verification**
* Confirms `/v1/chat/completions` streams compliant SSE delta chunks.


* Verifies HTTP 401 Unauthorized responses when the local bearer token is omitted.


* Validates that requests bearing external browser `Origin` headers are blocked by CSPA defenses.