# Runbook — Entraclaw MCP dies after a few minutes under sustained activity

**Status:** OPEN — not yet root-caused. Two contributing amplifiers shipped
and merged (PR #40, PR #41). The underlying "parent Claude CLI reaps a
healthy child after a few minutes of Teams/email push traffic" symptom has
reduced in frequency but **not been eliminated**.

**Owner rotation:** Anyone picking this up next — read this doc end to end
before running anything. Do NOT start from scratch.

**Last update:** 2026-04-24 (after PR #40 + PR #41 merged).

---

## TL;DR for the next agent

- **Symptom.** Entraclaw MCP server (stdio child of Claude Code CLI) becomes
  progressively slower, then disconnects entirely, typically within
  2–10 minutes of sustained activity (inbound Teams DMs, email poll cycles,
  or chat auto-discovery). The user's UX: first tool calls return in under
  a second; after a while they stall; then `/mcp` shows the server
  disconnected and a manual `Reconnect entraclaw` is required. The child
  process is reaped — no traceback, no shutdown log line, nothing in
  `~/.entraclaw/logs/entraclaw.log` marking the end.
- **What we tried.** (1) Debug stderr capture via wrapper script, (2) PR #40
  to stop entraclaw records double-rendering through FastMCP's root
  `RichHandler`, (3) PR #41 to stop the wrapper itself from retriggering
  the self-spawn cascade that PR #36 had originally killed, (4) removal of
  4 throttling-sleep tests that were masking the symptom in the test
  suite's own timings.
- **What remains broken.** Parent Claude CLI at sustained 27–83% CPU and
  ~1 GB RSS while entraclaw is active. Zero tracebacks surface on the
  parent-reaped MCP child — consistent with "CLI stopped draining stdout
  and eventually SIGKILLed the child," not with a crash on the child's
  side. Blob-write-on-push hot path (3–5 synchronous HTTP calls per
  inbound Teams message) is still on the critical path and remains the
  leading suspect amplifier.
- **Before doing ANYTHING else.** Read **Learning #37** (self-spawn
  cascade), **Learning #38** (leader-cache overwrite), **Learning #45**
  (wrapper bypass), **Learning #36** (sub-agent worktree pip install),
  and **Learning #39** (dev-channel flag typo). All five are regressions
  that have *already happened once* against this exact symptom shape and
  that the next agent will be tempted to re-debug from zero. Don't.

---

## Symptom details

### What the user sees

1. `/mcp` shows entraclaw as `connected`.
2. First 1–3 tool calls (e.g., `whoami`, `read_teams_messages`) respond
   in under a second.
3. After some time — anywhere from ~2 minutes of idle up to ~10 minutes
   of active use — subsequent tool calls stall for 5–60 seconds and then
   fail with a generic transport error.
4. `/mcp` now shows entraclaw as `disconnected`.
5. Manually running `/mcp` → `Reconnect entraclaw` (or any tool-call
   attempt) respawns the child; the cycle repeats.

### What the logs show

- `~/.entraclaw/logs/entraclaw.log` (the JSON file log): normal INFO lines
  right up until the cutoff. **No shutdown/exception line at the tail.**
  The log simply stops.
- `/tmp/entraclaw-debug.log` (stderr tee from the debug wrapper — only
  present if the wrapper is active via `.mcp.json`'s `command`):
  httpx request/response lines, msal token refresh lines, FastMCP
  lifecycle `Starting MCP server "entraclaw"` banners. **Zero Python
  tracebacks on the parent MCP child around the time of drop.** The
  only `BrokenPipeError` tracebacks ever captured in this log belong
  to the *cascade children* that Learning #45 fixed, not to the parent
  MCP process itself.
- `ps aux | grep claude` while it's happening: parent Claude CLI at 27%
  to 83% CPU, ~800 MB–1 GB RSS, state `S+`. Entraclaw child at ~0% CPU.

### Process and config at time of writing

- `.mcp.json` `command` is `.venv/bin/entraclaw-mcp` (direct, no wrapper).
  The wrapper (`scripts/entraclaw-mcp-debug.sh`) is fix-ready and carries
  the self-ref marker (Learning #45 / PR #41) — **you can safely flip
  `.mcp.json` back to the wrapper** to capture stderr without
  retriggering the twin-spawn cascade.
- Claude CLI launch flag is the correct double-dash form:
  `--dangerously-load-development-channels server:entraclaw`.
  Learning #39 rules out the single-dash typo as the cause of any
  channel-delivery symptom.
- Three background tasks are active in agent_user mode: Teams poll (5s),
  email poll (60s), chat auto-discovery (120s), plus the daily-summary
  scheduler. Persona-sati MCP is listed as an SSE peer in `.mcp.json`
  and is fetched at boot.

---

## What has been tried (and merged)

### Amplifier #1 — Wrapper-triggered self-spawn cascade (FIXED by PR #41)

When the debug wrapper `scripts/entraclaw-mcp-debug.sh` was named as
`.mcp.json`'s `command`, entraclaw boot spawned a duplicate child ~2s in
via the efferent-copy `discover_sinks` logic. The duplicate completed a
full three-hop token flow, registered polls, fetched the persona-sati
prompt, responded to `tools/list`, and then died on BrokenPipeError when
the parent tore down the stdio_client. Each boot pair did **2× the API
work** — two token flows, two poll registrations, two Graph chat lookups
— burning login.microsoftonline.com round-trips pointlessly.

**Root cause.** `_is_self_referential_peer` compared `peer.command`
against `sys.argv[0]`. The wrapper script's resolved path did not match
`.venv/bin/entraclaw-mcp`, so the self-ref check returned `False` and
the peer was NOT filtered.

**Fix.** `_is_self_referential_peer` now reads up to 16 KB of the
wrapper script, looks for a `# entraclaw-self-ref-target: <path>`
marker line, and compares the declared target against `sys.argv[0]` /
`sys.executable`. `scripts/entraclaw-mcp-debug.sh` now carries the
marker. Shipped in commit `934bbef`, merged as PR #41.

**Effect on the disconnect symptom.** Eliminated the twin-spawn API
doubling. The disconnect symptom *reduced* in frequency but did not
disappear.

See: `docs/runbooks/hard-won-learnings.md` Learning #45.

### Amplifier #2 — Double-rendered logs flooding stderr (FIXED by PR #40)

Every record logged to the `entraclaw` logger propagated up to the
Python root logger, where FastMCP's `configure_logging()` had installed
a `RichHandler` via `logging.basicConfig`. Result: every entraclaw log
record was rendered **twice** on stderr — once as JSON via our own
StreamHandler, once as rich-formatted pretty-print via FastMCP's root
handler. The parent Claude CLI had to drain 2× the byte volume over
stdio/stderr, and in periods of message bursts this was plausibly
contributing to stdio backpressure.

**Fix.** Added `logger.propagate = False` in
`src/entraclaw/logging_config.py`. Shipped in commit `41ae30b`, merged
as PR #40. `pytest` regressed on 6 `caplog` tests because caplog
attaches a handler to root (not to the entraclaw logger), and with
propagation off, entraclaw records never reached caplog. Fixed by
adding an autouse fixture in `tests/conftest.py` that attaches
`caplog.handler` directly to `entraclaw_logger` per test.

**Known limitation.** Only `entraclaw.*` records stop propagating.
`httpx.*` and `msal.*` records still propagate to root and still render
through the RichHandler. Given the Teams poll fires once every 5s and
issues at least one httpx request per cycle, the remaining stderr
volume from these third-party loggers is material but not measured.

**Effect on the disconnect symptom.** Halved entraclaw-originated
stderr volume. Symptom reduced but not eliminated.

### Amplifier #3 — 4 slow throttling tests in the test suite (REMOVED)

Not directly related to the runtime disconnect; removed per user
instruction because they were dominating the test-suite wall clock
(357s of real `time.sleep()` through `Retry-After` intervals, pushing
the suite past the default Bash 300s timeout). Removed in PR #40:

- `TestCreateOrFindChat::test_rate_limited`
- `TestTeamsSend::test_rate_limited`
- `TestUpdatePlaceholder::test_rate_limited_raises`
- `TestDeleteChatMessage::test_raises_rate_limit_on_429`

The `RateLimitError` import was left in because the production code
still raises it; only the tests were removed.

### Debug infrastructure — stderr capture via wrapper (READY, OFF BY DEFAULT)

`scripts/entraclaw-mcp-debug.sh` tees stderr to
`/tmp/entraclaw-debug.log` with `===== wrapper start <UTC> pid=<n> =====`
markers. Since PR #41 it carries the self-ref marker and is safe to
activate. To turn it on: change `.mcp.json`'s `command` from
`.venv/bin/entraclaw-mcp` to `scripts/entraclaw-mcp-debug.sh` and
restart Claude Code. To turn it off: revert the command. The log is a
tee, not a redirect — server stderr still flows to the parent.

---

## Hypotheses ranked by remaining likelihood

1. **Parent Claude CLI stdio-drain backpressure (PRIMARY).** The
   Claude CLI's MCP client renders tool activity through its own UI
   layer (SSE to the Anthropic API, markdown repainting, tool-schema
   validation) on every stdio frame. When entraclaw emits bursts of
   structured output during a busy Teams push, the CLI's render budget
   can saturate — CPU climbs to 80%+, the stdout pipe from the child
   stops being drained, and after enough time the CLI reaps the child
   rather than blocking. **Evidence for:** zero child tracebacks,
   sustained parent CPU, the "first tool calls fast, then slower, then
   dropped" shape. **Against:** we have no direct measurement of the
   parent's read side. This is the leading theory but it is a theory.
2. **Blob write on Teams push hot path.** Every inbound Teams message
   triggers `interaction_log.append()`, which in `BlobBackend` mode
   does a token check + blob GET + blob PUT with ETag concurrency —
   3–5 synchronous HTTPS round-trips per push. Under message bursts,
   these are serial and can pin an event-loop task. If the push path
   is blocked on blob I/O, the MCP `notifications/claude/channel`
   push is delayed, which the parent CLI may time out on. **Evidence
   for:** empirically correlates with activity. **Against:** blob
   calls would generate visible 429/5xx on the child side if they
   were the issue, and we don't see those.
3. **httpx/msal logs still propagating.** PR #40 fixed entraclaw's
   own propagation but third-party loggers still render through the
   root `RichHandler`. On a busy poll cycle this is still a few
   hundred bytes per 5 seconds, most of it pretty-printed. Worth
   silencing for completeness; unlikely on its own to account for the
   drops.
4. **Persona-sati SSE fetch blocking boot.** `_load_agent_instructions`
   opens an SSE connection to persona-sati at boot to fetch the
   system prompt. If the pod is slow or flapping, boot stalls before
   stdio is even live. **Evidence for:** some cold-start slow cases
   fit this. **Against:** the boot banners always appear and the
   initial few tool calls succeed — this theory would predict dead-on-
   arrival, not "fine then dies." Lower likelihood but easy to rule
   out by setting `PERSONA_SATI_MCP_URL=` (empty) briefly.
5. **Token refresh thrashing.** Eager 55-min refresh + lazy 401 retry
   could occasionally overlap. Low likelihood given the observed
   cadence of drops is minutes, not matches of the refresh interval.
6. **Eager init of all three polls at boot.** `_init_poll` starts
   Teams poll + email poll + chat discovery all at `start`. A fresh
   boot thus does a token acquisition, a `/me/chats` enumeration, a
   `/me/messages` enumeration, and a first Teams poll in the first
   few seconds — high concurrent HTTP. Not itself a cause of steady-
   state drops but amplifies cold-start stress.

### Ruled out (don't re-investigate)

- **Efferent-copy self-spawn cascade.** Killed in PR #36 (direct) and
  PR #41 (wrapper). Both covered by regression tests.
- **Learning #36 venv corruption.** `python -c "from entraclaw import
  config; print(config.__file__)"` currently resolves to the parent
  src tree, not a worktree. Do re-check if symptoms resurface after
  any sub-agent dispatch (see CLAUDE.md non-negotiable).
- **Learning #44 parent-rename venv orphan.** `pyvenv.cfg` and venv
  shebangs all resolve to the current repo path. Verified post-PR #41.
- **Learning #39 dev-channel flag typo.** Confirmed the Claude CLI is
  running with `--dangerously-load-development-channels` (double dash,
  see `ps` output in the "Process and config" section above).

---

## What to try next — ordered by cost/value

### Step 1 — Quantify, don't theorize

Flip `.mcp.json` back to the wrapper to re-enable `/tmp/entraclaw-debug.log`
capture. Wait until the next drop, then gather:

```bash
# Size of stderr over the session
wc -c /tmp/entraclaw-debug.log

# Rate (lines/second) per minute of life
awk '/wrapper start/{t=$NF} {print t}' /tmp/entraclaw-debug.log | \
    sort | uniq -c

# Python traceback count on the parent process (as opposed to cascade children)
grep -c "BrokenPipeError" /tmp/entraclaw-debug.log

# Wrapper start count — should equal /mcp-reconnect count,
# NOT 2× that (Learning #45 regression signal)
grep -c "wrapper start" /tmp/entraclaw-debug.log
```

Goals: (a) is the stderr rate actually large (e.g., >10 KB/min)
or is it steady-state low and only the CPU that's climbing? (b) do
the drops coincide with a specific event type (Teams push burst,
email poll, token refresh)? (c) is the wrapper-start count still 1-per-
reconnect or has Learning #45 regressed again?

### Step 2 — Silence third-party loggers (cheap)

Extend `src/entraclaw/logging_config.py` to set `propagate = False` on
`httpx` and `msal` loggers too (or set their level to `WARNING` on
root). Ship as a follow-on commit. Re-measure stderr rate from Step 1.

### Step 3 — Decouple blob I/O from the push hot path (medium)

Currently `_push_channel_notification` path runs synchronously with
`interaction_log.append()`, which does blob I/O. Decouple via an
asyncio queue with a background consumer. The push returns immediately
after enqueue; the queue consumer handles blob writes with retry. Two
tests needed first: (a) the queue drains under normal load without
dropping; (b) if the queue backpressures, the push still returns fast.
**Before writing the code, confirm that the push path is actually
blocking on blob I/O by adding a `time.perf_counter()` span around the
blob call and logging slow ones.**

### Step 4 — Try SSE transport (experimental)

FastMCP supports SSE transport. Run entraclaw as a standalone SSE
server (`entraclaw-mcp --transport sse --port 8101` if available, or
add the wiring), and point `.mcp.json` at `http://localhost:8101/sse`
instead of stdio. This eliminates the parent-CLI stdio-pipe saturation
theory entirely. **If the symptom disappears under SSE**, the
hypothesis #1 (parent CLI backpressure) is confirmed and the
remediation is either to (a) stay on SSE, or (b) reduce stdio output
volume and frame rate on the stdio path.

### Step 5 — Get a `py-spy` dump of the parent Claude CLI mid-drop

`py-spy dump --pid $PARENT_PID` (or the Claude CLI's Node-equivalent
if it's a Node process, which it is — `node --inspect` + Chrome
devtools) to see what the parent is doing when entraclaw appears
stuck. This is the most diagnostic but most invasive step. Do it
after Steps 1–3 have tightened the hypothesis.

### Step 6 — File an upstream issue if it's the CLI

If Step 4 shows SSE is clean and stdio is not, and Step 5 shows the
parent CLI stuck in its own render path: file an issue against Claude
Code with the captured py-spy output and a minimal reproduction.
Mitigation for this repo: recommend SSE transport in `.mcp.json`.

---

## DO NOT suggest before reading prior debugging

These are all theories that have already been investigated and ruled
out or already fixed. Do not propose them as new ideas:

- "Maybe the server is crashing" — **No.** No tracebacks on the parent
  child; the log just stops. It is being reaped, not crashing.
- "Maybe it's the self-spawn cascade" — **Ruled out.** PR #36 + PR #41
  with regression tests. Verify by checking wrapper-start pair cadence
  (Learning #45), but don't re-debug from zero.
- "Maybe the leader/slave gate is dropping pushes" — **Ripped out.**
  See Learning #38 and PR #36. Channel pushes fire unconditionally now.
- "Maybe it's the dev-channel launch flag" — **Ruled out.** The running
  CLI process has the correct double-dash flag; see Learning #39.
- "Maybe the venv got corrupted" — **Ruled out.** `config.__file__`
  resolves to the parent src tree, not a worktree (Learning #36 check)
  and not a renamed path (Learning #44 check).
- "The test suite is slow so something's wrong with the runtime" —
  The 4 throttling tests were intentionally slow because they were
  testing real `Retry-After` sleeps. Removed in PR #40 for suite-speed,
  not because they signaled a runtime problem.

---

## What to preserve in any fix

- Every tool call must still be audit-logged before execution. The blob
  write is security-relevant; do not "fix" the hot path by skipping it.
  If you decouple via a queue, the audit write must still be durable
  before the tool's side effect is visible externally.
- `logger.propagate = False` must stay on `entraclaw`. Do not revert
  that fix in the process of silencing third-party loggers.
- `_is_self_referential_peer`'s wrapper-marker behavior is a
  security-relevant invariant now (see Learning #45). Any change to
  efferent-copy discovery must include regression tests that prove
  both direct and wrapper-indirect self-peers are skipped.
- The debug wrapper is opt-in. Don't make it the default in `.mcp.json`
  on `main`; it writes to `/tmp/entraclaw-debug.log` which is a
  single-user, single-machine convention. Leave that switch as a
  conscious flip for active debugging.

---

## Cross-references

- `docs/runbooks/hard-won-learnings.md` Learning #36 (venv corruption)
- `docs/runbooks/hard-won-learnings.md` Learning #37 (self-spawn cascade)
- `docs/runbooks/hard-won-learnings.md` Learning #38 (leader-cache overwrite)
- `docs/runbooks/hard-won-learnings.md` Learning #39 (dev-channel flag typo)
- `docs/runbooks/hard-won-learnings.md` Learning #44 (parent-rename venv orphan)
- `docs/runbooks/hard-won-learnings.md` Learning #45 (wrapper bypass)
- `docs/runbooks/hard-won-learnings.md` Learning #46 (this symptom — pointer)
- `docs/engineering-status.md` "What's New Apr 24 (part 2) — MCP disconnect investigation" section
- `src/entraclaw/logging_config.py` (`propagate = False` fix from PR #40)
- `src/entraclaw/efferent_copy.py` (`_is_self_referential_peer` from PR #36 + PR #41)
- `scripts/entraclaw-mcp-debug.sh` (debug wrapper, safe to activate)
