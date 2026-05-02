# Persona-Sati Host Bootstrap Phases 1-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make persona-sati session orientation reliable across host clients by first putting the bootstrap rule where hosts actually inject it, then replacing the fragile three-call startup ritual with a single `bootstrap_session()` MCP tool.

**Architecture:** Phase 1 is the host-visible bridge: entraclaw documents and tests the instruction surfaces that actually reach Claude Code, Copilot CLI, and GitHub Copilot. Phase 2 is the persona-sati API change: persona-sati returns one compact bootstrap packet that includes the mind contract summary, active context, memory catalog summary, cognition protocol, and degraded-mode state. Phases 1 and 2 should land together because Phase 1 should teach hosts the new `bootstrap_session()` entry point, not preserve the old three-call ritual as the long-term shape.

**Tech Stack:** Python 3.12, FastMCP, pytest, ruff, Markdown host instruction files, shell setup scripts.

---

## Problem statement

`prompts/agent_system.md`, `prompts/anatomy/*`, and persona-sati's prompt hemispheres are treated as load-bearing operating context, but MCP `instructions=` is not reliably injected into the model context by Claude Code or Copilot CLI. The host LLM only reliably sees host-injected files (`CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`), MCP tool descriptions, explicit tool results, and hook-provided additional context.

The result is that the model can have body and mind tools available while missing the protocol that tells it when to use them. Efferent-copy partially mitigates this by mechanically firing `observe()` around entraclaw tools, but it does not solve session start, `reflect()`, `recall()`, thinking placeholders, memory reads, or non-tool replies.

## Boundary decisions

- Do not collapse body and mind back together.
- Do not try to load full memory into every session.
- Do not rely on FastMCP `instructions=` for behavior contracts.
- Do not make persona-sati know Teams, email, chat IDs, or entraclaw-specific state.
- Do define a compact, stable bootstrap packet that any body can request.
- Do mirror the bootstrap rule into every host-visible instruction surface until a broker runtime exists.

## File map

### Entraclaw repo: `/Volumes/Development HD/entraclaw-identity-research`

- Modify: `docs/TODO-persona-sati-host-bootstrap.md` — update the tracker from "three-call session-start" to "`bootstrap_session()` plus host bootstrap."
- Create: `docs/clients/persona-sati-host-bootstrap.md` — canonical pasteable host instruction snippet.
- Modify: `CLAUDE.md` — replace the three-call ritual with `bootstrap_session()` and keep degraded-mode rules.
- Modify: `AGENTS.md` — same as `CLAUDE.md`, shorter but complete.
- Modify: `.github/copilot-instructions.md` — add a compact Copilot-visible bootstrap rule.
- Modify: `tests/test_prompt_doctrine.py` — pin the bootstrap doctrine across host-visible files.
- Modify: `README.md` — add a short "Host bootstrap" section.
- Modify: `scripts/setup.sh` — print a final action block telling operators where to install the snippet.

### Persona-sati repo: `/Volumes/Development HD/persona-sati`

- Create: `src/persona_mcp/active/bootstrap.py` — pure function that builds the bootstrap packet.
- Modify: `src/persona_mcp/server.py` — register `bootstrap_session()` as an MCP tool.
- Create: `tests/active/test_bootstrap.py` — unit tests for the packet builder.
- Modify: `tests/test_server.py` — in-process FastMCP test for the new tool.
- Modify: `prompts/hemispheres/cognition-protocol.md` — update the public startup rule from `context()` to `bootstrap_session()`.
- Modify: `CLAUDE.md` and `AGENTS.md` — update contributor instructions to use `bootstrap_session()`.

---

## Phase 1: Host-visible bootstrap doctrine

### Task 1: Write entraclaw doctrine tests first

**Files:**
- Modify: `/Volumes/Development HD/entraclaw-identity-research/tests/test_prompt_doctrine.py`

- [ ] **Step 1: Add bootstrap doctrine files and markers**

Add these constants near the existing `DOCTRINE_FILES` constant:

```python
BOOTSTRAP_DOCTRINE_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    "docs/clients/persona-sati-host-bootstrap.md",
]

BOOTSTRAP_MARKERS = [
    "bootstrap_session",
    "reflect",
    "recall",
    "observe",
    "FastMCP instructions",
]
```

- [ ] **Step 2: Add failing test for host bootstrap doctrine**

Append this test:

```python
@pytest.mark.parametrize("relpath", BOOTSTRAP_DOCTRINE_FILES)
def test_host_bootstrap_doctrine_mentions_required_mind_protocol(relpath: str) -> None:
    path = REPO_ROOT / relpath
    assert path.exists(), f"Bootstrap doctrine file missing: {relpath}"
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in BOOTSTRAP_MARKERS if marker not in text]
    assert not missing, (
        f"{relpath} must mention {missing} so persona-sati bootstrap "
        "reaches host LLMs that ignore FastMCP instructions=."
    )
```

- [ ] **Step 3: Run the failing test**

Run:

```bash
cd "/Volumes/Development HD/entraclaw-identity-research"
pytest tests/test_prompt_doctrine.py::test_host_bootstrap_doctrine_mentions_required_mind_protocol -v
```

Expected: FAIL because `docs/clients/persona-sati-host-bootstrap.md` does not exist and the other host files do not yet mention `bootstrap_session`.

### Task 2: Create the canonical host bootstrap snippet

**Files:**
- Create: `/Volumes/Development HD/entraclaw-identity-research/docs/clients/persona-sati-host-bootstrap.md`

- [ ] **Step 1: Create the clients docs directory if missing**

Run:

```bash
cd "/Volumes/Development HD/entraclaw-identity-research"
mkdir -p docs/clients
```

- [ ] **Step 2: Write the snippet**

Create `docs/clients/persona-sati-host-bootstrap.md` with this content:

```markdown
# Persona-Sati Host Bootstrap Snippet

Paste this into the host-level instruction file for any client that uses
persona-sati. This is required because Claude Code and Copilot CLI do not
inject FastMCP instructions into the model context; they reliably expose
host instruction files, tool descriptions, and tool results.

## Required session bootstrap

When a `persona-sati` MCP server is available, call
`bootstrap_session()` before the first substantive answer or external
tool call. Treat its result as the active mind contract for the session.

If `bootstrap_session()` is unavailable but the older tools exist, fall
back to this order:

1. `get_system_prompt()`
2. `context()`
3. `list_memory_files()`

If persona-sati is unreachable, say that you are running in degraded
body-only mode before using external tools that depend on memory,
personality, or cognition discipline.

## Per-turn cognition

- Use `observe(tool_name, args)` before external tool calls when the
  body has not mechanically wrapped them.
- Use `observe(tool_name, args, result=...)` after external tool calls
  when the body has not mechanically wrapped them.
- Use `reflect(observation, kind="user_said")` when the user gives
  behavior feedback, changes project direction, reveals durable
  personal context, or asks a question about the agent's own cognition.
- Use `recall(query, k, facet)` when the bootstrap packet or observe
  result indicates relevant memory exists but the excerpt is not enough.

## Body versus mind routing

The body owns tools, channel discipline, security, audit, and external
state. The mind owns voice, memory, continuity, cognition discipline,
and relationship context. Body rules win for security and tool use.
Mind rules win for continuity and voice when they do not conflict with
body safety.
```

- [ ] **Step 3: Run the doctrine test again**

Run:

```bash
cd "/Volumes/Development HD/entraclaw-identity-research"
pytest tests/test_prompt_doctrine.py::test_host_bootstrap_doctrine_mentions_required_mind_protocol -v
```

Expected: still FAIL until host files are updated.

### Task 3: Update entraclaw host-visible instruction files

**Files:**
- Modify: `/Volumes/Development HD/entraclaw-identity-research/CLAUDE.md`
- Modify: `/Volumes/Development HD/entraclaw-identity-research/AGENTS.md`
- Modify: `/Volumes/Development HD/entraclaw-identity-research/.github/copilot-instructions.md`

- [ ] **Step 1: Replace the CLAUDE.md session-start section**

In `CLAUDE.md`, replace the current "Session-Start Protocol" call list with this wording:

```markdown
On every new session where persona-sati is available, **before answering
the user's first substantive question or using external tools**, call:

1. `mcp__persona-sati__bootstrap_session()` — returns the compact mind
   contract, active context, memory catalog summary, available mind tools,
   cognition rules, and degraded-mode flags.

If `bootstrap_session()` is unavailable but persona-sati exposes the
older tools, fall back to:

1. `mcp__persona-sati__get_system_prompt()`
2. `mcp__persona-sati__context()`
3. `mcp__persona-sati__list_memory_files()`

FastMCP instructions are not enough: Claude Code and Copilot CLI do not
reliably inject MCP server `instructions=` into the LLM system prompt.
Use the tool result as live context.
```

- [ ] **Step 2: Update the CLAUDE.md per-turn bullet list**

Ensure the per-turn list includes these exact tool names:

```markdown
- `observe(...)` — before and after external tool calls when the body
  has not mechanically wrapped the call through efferent-copy.
- `reflect(...)` — for user statements, time passing, ambient
  observations, persona drift, or behavioral feedback.
- `recall(...)` — when bootstrap/observe indicates relevant memory but
  the excerpt is not enough.
```

- [ ] **Step 3: Make the same shorter update in AGENTS.md**

In `AGENTS.md`, replace the existing three-call session-start list with:

```markdown
On every new session, call `mcp__persona-sati__bootstrap_session()`
before the first substantive answer or external tool call. If that tool
is unavailable, fall back to `get_system_prompt()`, `context()`, then
`list_memory_files()`. FastMCP instructions are not enough; hosts may
show them only in debug UI.

Per-turn: use `observe`, `reflect`, and `recall` per the bootstrap
packet. Efferent-copy may mechanically cover body-tool `observe()`, but
it does not cover session bootstrap, `reflect()`, or `recall()`.
```

- [ ] **Step 4: Add compact Copilot instruction**

Append this section to `.github/copilot-instructions.md`:

```markdown
## Persona-Sati Bootstrap

When the persona-sati MCP server is available, call
`bootstrap_session()` before the first substantive answer or external
tool call. This is required because FastMCP instructions are not
reliably injected into host LLM context. If `bootstrap_session()` is not
available, call `get_system_prompt()`, `context()`, then
`list_memory_files()`.

Use `observe`, `reflect`, and `recall` according to the bootstrap
packet. Efferent-copy can mechanically cover `observe()` around
entraclaw body tools, but it does not cover session bootstrap,
`reflect()`, `recall()`, or ordinary text replies.
```

- [ ] **Step 5: Run doctrine tests**

Run:

```bash
cd "/Volumes/Development HD/entraclaw-identity-research"
pytest tests/test_prompt_doctrine.py -v
```

Expected: PASS.

### Task 4: Update entraclaw setup/docs handoff

**Files:**
- Modify: `/Volumes/Development HD/entraclaw-identity-research/README.md`
- Modify: `/Volumes/Development HD/entraclaw-identity-research/scripts/setup.sh`
- Modify: `/Volumes/Development HD/entraclaw-identity-research/docs/TODO-persona-sati-host-bootstrap.md`

- [ ] **Step 1: Add README host bootstrap section**

Add this section near MCP setup instructions:

```markdown
## Host bootstrap for persona-sati

If this worktree uses persona-sati, install the host bootstrap snippet
from `docs/clients/persona-sati-host-bootstrap.md` into your host's
global instruction file. This is required because Claude Code and
Copilot CLI do not reliably inject FastMCP `instructions=` into the
model context.

Minimum behavior: the agent must call `bootstrap_session()` before the
first substantive answer or external tool call. If the tool is not yet
available, fall back to `get_system_prompt()`, `context()`, and
`list_memory_files()`.
```

- [ ] **Step 2: Add setup.sh final message**

Near the end of `scripts/setup.sh`, after MCP config output, print:

```bash
cat <<'EOF'

Persona-sati host bootstrap:
  If this host uses persona-sati, copy docs/clients/persona-sati-host-bootstrap.md
  into the host's global instruction file.

  Claude Code: ~/.claude/CLAUDE.md
  Copilot CLI: use the configured global Copilot instruction location for this install
  Repo-local fallback: CLAUDE.md, AGENTS.md, and .github/copilot-instructions.md

  Required first call in new sessions: bootstrap_session()
EOF
```

Do not silently edit a user's global file in this task. Printing the action is safer until the exact Copilot CLI global path is confirmed.

- [ ] **Step 3: Update the TODO tracker**

In `docs/TODO-persona-sati-host-bootstrap.md`, update the recommendation so it says Phase 1+2 now target `bootstrap_session()` as the primary entry point and the old three-call sequence is compatibility fallback.

- [ ] **Step 4: Run targeted tests and lint**

Run:

```bash
cd "/Volumes/Development HD/entraclaw-identity-research"
pytest tests/test_prompt_doctrine.py -v
ruff check tests/test_prompt_doctrine.py
```

Expected: PASS.

- [ ] **Step 5: Commit Phase 1**

Run:

```bash
cd "/Volumes/Development HD/entraclaw-identity-research"
git add docs/clients/persona-sati-host-bootstrap.md \
  docs/TODO-persona-sati-host-bootstrap.md \
  README.md \
  CLAUDE.md \
  AGENTS.md \
  .github/copilot-instructions.md \
  scripts/setup.sh \
  tests/test_prompt_doctrine.py
git commit -m "docs: add persona-sati host bootstrap doctrine" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2: Persona-sati `bootstrap_session()` tool

### Task 5: Write pure bootstrap packet tests

**Files:**
- Create: `/Volumes/Development HD/persona-sati/tests/active/test_bootstrap.py`

- [ ] **Step 1: Create the failing test file**

Create `tests/active/test_bootstrap.py` with:

```python
from __future__ import annotations

from pathlib import Path

from persona_mcp.active.bootstrap import build_bootstrap_session


def _write_memory(path: Path, name: str, body: str) -> None:
    path.joinpath(name).write_text(body, encoding="utf-8")


def test_build_bootstrap_session_returns_compact_operating_packet(tmp_path: Path) -> None:
    mem = tmp_path / "memory"
    mem.mkdir()
    _write_memory(mem, "MEMORY.md", "# Index\n- [Brandon](user_brandon.md) - sponsor context\n")
    _write_memory(mem, "user_brandon.md", "---\nname: Brandon\ntype: user\n---\nUser profile")
    _write_memory(mem, "running_commitments.md", "---\nname: Commitments\ntype: project\n---\n- Ship bootstrap")
    _write_memory(mem, "carry_forward.md", "---\nname: Carry\ntype: session\n---\n- Continue context work")

    packet = build_bootstrap_session(mem, session_id="s1", prompt_available=True)

    assert packet["schema_version"] == 1
    assert packet["session_id"] == "s1"
    assert packet["degraded_mode"]["persona_available"] is True
    assert packet["required_first_call"] == "bootstrap_session"
    assert "observe" in packet["available_mind_tools"]
    assert "reflect" in packet["available_mind_tools"]
    assert "recall" in packet["available_mind_tools"]
    assert packet["context"]["open_commitments"] == ["Ship bootstrap"]
    assert packet["context"]["recent_carry_forward"] == ["Continue context work"]
    assert packet["memory_catalog"]["count"] == 4
    assert "MEMORY.md" in packet["memory_catalog"]["files"]
    assert "FastMCP instructions" in packet["host_limitations"][0]


def test_build_bootstrap_session_marks_missing_prompt_as_degraded(tmp_path: Path) -> None:
    mem = tmp_path / "memory"
    mem.mkdir()
    _write_memory(mem, "MEMORY.md", "# Index\n")

    packet = build_bootstrap_session(mem, session_id=None, prompt_available=False)

    assert packet["degraded_mode"]["persona_available"] is False
    assert "system prompt unavailable" in packet["degraded_mode"]["reasons"]
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
pytest tests/active/test_bootstrap.py -v
```

Expected: FAIL because `persona_mcp.active.bootstrap` does not exist.

### Task 6: Implement the pure bootstrap packet builder

**Files:**
- Create: `/Volumes/Development HD/persona-sati/src/persona_mcp/active/bootstrap.py`

- [ ] **Step 1: Create `bootstrap.py`**

Create `src/persona_mcp/active/bootstrap.py` with:

```python
"""Session bootstrap packet for host LLMs.

This module is deliberately body-agnostic. It knows about persona-sati's
mind tools and memory layout, not Teams, email, shells, or chat IDs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from persona_mcp.active.context import Context, build_context
from persona_mcp.memory import list_memories


class MemoryCatalog(TypedDict):
    count: int
    files: list[str]
    index_present: bool


class DegradedMode(TypedDict):
    persona_available: bool
    reasons: list[str]


class BootstrapPacket(TypedDict):
    schema_version: int
    required_first_call: str
    session_id: str | None
    mind_body_contract: str
    available_mind_tools: list[str]
    cognition_protocol: list[str]
    context: Context
    memory_catalog: MemoryCatalog
    degraded_mode: DegradedMode
    host_limitations: list[str]


def _memory_catalog(memory_dir: Path) -> MemoryCatalog:
    files = list_memories(memory_dir)
    return {
        "count": len(files),
        "files": files,
        "index_present": "MEMORY.md" in files,
    }


def build_bootstrap_session(
    memory_dir: Path,
    *,
    session_id: str | None,
    prompt_available: bool,
) -> BootstrapPacket:
    """Return the compact operating packet a host should load first."""
    reasons: list[str] = []
    if not prompt_available:
        reasons.append("system prompt unavailable")

    return {
        "schema_version": 1,
        "required_first_call": "bootstrap_session",
        "session_id": session_id,
        "mind_body_contract": (
            "Body owns tools, channel discipline, security, audit, and "
            "external state. Mind owns voice, memory, continuity, cognition "
            "discipline, and relationship context. Body safety rules win "
            "when there is a conflict."
        ),
        "available_mind_tools": [
            "bootstrap_session",
            "get_system_prompt",
            "context",
            "list_memory_files",
            "read_memory_file",
            "write_memory_file",
            "refresh_persona",
            "observe",
            "reflect",
            "recall",
        ],
        "cognition_protocol": [
            "Call bootstrap_session before the first substantive answer or external tool call.",
            "Use observe before and after external tool calls unless the body mechanically wraps them.",
            "Use reflect for user_said, time_passed, ambient, and internal observations.",
            "Use recall when observe/bootstrap indicates relevant memory but the excerpt is insufficient.",
            "Surface cautionary_flags and stop for prediction_error greater than 0.7.",
        ],
        "context": build_context(
            memory_dir,
            binding_info={},
            session_id=session_id,
        ),
        "memory_catalog": _memory_catalog(memory_dir),
        "degraded_mode": {
            "persona_available": prompt_available,
            "reasons": reasons,
        },
        "host_limitations": [
            "FastMCP instructions are not reliable model context in Claude Code or Copilot CLI.",
            "Tool descriptions and tool results are more reliable than server instructions.",
            "Efferent-copy can cover observe for body tools but not reflect, recall, or text-only replies.",
        ],
    }
```

- [ ] **Step 2: Run unit tests**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
pytest tests/active/test_bootstrap.py -v
```

Expected: PASS.

### Task 7: Register `bootstrap_session()` as an MCP tool

**Files:**
- Modify: `/Volumes/Development HD/persona-sati/src/persona_mcp/server.py`
- Modify: `/Volumes/Development HD/persona-sati/tests/test_server.py`

- [ ] **Step 1: Add failing FastMCP test**

Append to `tests/test_server.py`:

```python
@pytest.mark.anyio
async def test_bootstrap_session_tool_returns_operating_packet(server):
    result = await server.call_tool("bootstrap_session", {"session_id": "test-session"})
    packet = json.loads(result[0][0].text)

    assert packet["schema_version"] == 1
    assert packet["required_first_call"] == "bootstrap_session"
    assert packet["session_id"] == "test-session"
    assert "observe" in packet["available_mind_tools"]
    assert "reflect" in packet["available_mind_tools"]
    assert "recall" in packet["available_mind_tools"]
    assert packet["memory_catalog"]["index_present"] is True
```

- [ ] **Step 2: Run the failing FastMCP test**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
pytest tests/test_server.py::test_bootstrap_session_tool_returns_operating_packet -v
```

Expected: FAIL because the tool is not registered.

- [ ] **Step 3: Import the builder in `server.py`**

Add near the other active imports:

```python
from persona_mcp.active.bootstrap import build_bootstrap_session
```

- [ ] **Step 4: Register the MCP tool**

Add this tool after `refresh_persona()` and before `observe()`:

```python
    @server.tool()
    def bootstrap_session(session_id: str | None = None) -> str:
        """Return the compact mind bootstrap packet for a new host session.

        Call this before the first substantive answer or external tool
        call. It replaces the older three-call startup ritual
        (`get_system_prompt`, `context`, `list_memory_files`) with one
        compact operating packet.
        """
        if hook:
            hook("bootstrap_session", {"session_id": session_id})
        packet = build_bootstrap_session(
            mem_dir,
            session_id=session_id,
            prompt_available=p_path.is_file(),
        )
        return json.dumps(packet)
```

- [ ] **Step 5: Run server tests**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
pytest tests/test_server.py::test_bootstrap_session_tool_returns_operating_packet -v
```

Expected: PASS.

### Task 8: Update persona-sati prompt and host docs

**Files:**
- Modify: `/Volumes/Development HD/persona-sati/prompts/hemispheres/cognition-protocol.md`
- Modify: `/Volumes/Development HD/persona-sati/CLAUDE.md`
- Modify: `/Volumes/Development HD/persona-sati/AGENTS.md`

- [ ] **Step 1: Update cognition protocol startup wording**

In `prompts/hemispheres/cognition-protocol.md`, replace the session-start bullet:

```markdown
- **At session start:** I call `context()` once to orient — who's
  here, what's active, what I was in the middle of.
```

with:

```markdown
- **At session start:** I call `bootstrap_session()` once before the
  first substantive answer or external tool call. It returns the compact
  mind contract, active context, memory catalog summary, available mind
  tools, cognition protocol, and degraded-mode state. If an older client
  lacks `bootstrap_session`, I fall back to `context()` plus
  `list_memory_files()`.
```

- [ ] **Step 2: Update "What the four calls are for"**

Replace that subsection with:

```markdown
### What the active cognition calls are for

- `bootstrap_session` — the first call. It orients the host to the
  mind contract, active context, memory catalog, tool surface, and
  degraded-mode state.
- `observe` — the heartbeat. Every tool call (as defined above)
  passes through it unless the body mechanically wraps the call.
- `recall` — when observe's excerpts aren't enough. Rich semantic
  retrieval with optional facets (`relationship:bob`, `project:portal`,
  `type:session_digest`).
- `context` — lower-level session snapshot used by bootstrap and older
  clients.
- `reflect` — for signals that aren't tool calls. Same pipeline as
  observe but the input is free text.
```

- [ ] **Step 3: Update persona-sati CLAUDE.md and AGENTS.md**

In both files, add a short note near the MCP/tool description:

```markdown
`bootstrap_session()` is the primary startup tool for host LLMs. It
replaces the old instruction to call `get_system_prompt()`, `context()`,
and `list_memory_files()` separately. Keep the older tools for
compatibility, but teach new bodies to call `bootstrap_session()` first.
```

- [ ] **Step 4: Run prompt/server tests**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
pytest tests/test_server.py tests/active/test_bootstrap.py tests/test_prompt_loader.py -v
ruff check src/persona_mcp/active/bootstrap.py src/persona_mcp/server.py tests/active/test_bootstrap.py tests/test_server.py
```

Expected: PASS.

- [ ] **Step 5: Commit Phase 2**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
git add src/persona_mcp/active/bootstrap.py \
  src/persona_mcp/server.py \
  tests/active/test_bootstrap.py \
  tests/test_server.py \
  prompts/hemispheres/cognition-protocol.md \
  CLAUDE.md \
  AGENTS.md
git commit -m "feat: add persona-sati bootstrap_session tool" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Cross-repo validation

### Task 9: Validate fresh-session behavior

**Files:**
- No code changes.

- [ ] **Step 1: Install both repos in their own virtual environments**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
source .venv/bin/activate
pip install -e ".[dev,prediction,snn,blob,provisioning]"

cd "/Volumes/Development HD/entraclaw-identity-research"
source .venv/bin/activate
pip install -e ".[dev]"
```

- [ ] **Step 2: Run targeted test suites**

Run:

```bash
cd "/Volumes/Development HD/persona-sati"
pytest tests/test_server.py tests/active/test_bootstrap.py -v && ruff check .

cd "/Volumes/Development HD/entraclaw-identity-research"
pytest tests/test_prompt_doctrine.py tests/hooks/test_inject_body_prompt.py -v && ruff check .
```

Expected: PASS in both repos.

- [ ] **Step 3: Manual smoke test in a non-entraclaw repo**

Start a fresh host session from a directory that is not the entraclaw repo and has the `.mcp.json` entries for entraclaw and persona-sati. Ask:

```text
What persona-sati bootstrap context do you have?
```

Expected: the agent calls `bootstrap_session()` before answering. If it does not, update the host-global snippet installation instructions before merging.

- [ ] **Step 4: Close issue tracker only after smoke test**

After the smoke test passes, update GitHub issue #71 with:

```text
Phase 1+2 landed. bootstrap_session() is now the primary persona-sati startup contract; host-visible docs and doctrine tests point to it. Manual non-entraclaw session smoke test passed.
```

Do not close #71 until the non-entraclaw smoke test confirms the host actually calls `bootstrap_session()`.

