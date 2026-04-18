# TODOS

## P1

### ADR-005 Phase 2: MemoryBackend protocol + Local/Blob impls
Land the next phase of cloud-hosted memory. Spec: `docs/decisions/005-cloud-hosted-memory.md` §"Implementation phases" (Phase 2 row). Define `MemoryBackend` protocol in `src/entraclaw/storage/backend.py` with `LocalBackend` (current behavior) and `BlobBackend` (uses Phase 1 `BlobStore`). Route `interaction_log.py`, `daily_summary.py`, and memory-file access through it. Driven by `ENTRACLAW_KEEP_MEMORY_LOCAL` env var.
- **Effort:** S (~150 LOC + tests)
- **Depends on:** Phase 1 (`f900ba1`, shipped)
- **Source:** ADR-005

### Test isolation: interaction_log tests leak into production blob when ENTRACLAW_BLOB_ENDPOINT is set
The `tmp_data_dir` fixture in `tests/tools/test_interaction_log.py` sets `ENTRACLAW_DATA_DIR` to a pytest tmp path but does NOT clear `ENTRACLAW_BLOB_ENDPOINT` / `ENTRACLAW_BLOB_CONTAINER`. Since Phase 2/5 routed `log_interaction` and `read_day` through `get_backend()`, the factory reads those env vars and returns `BlobBackend` — which hits the real production container and ignores the tmp_data_dir. Result: 10 tests in `test_interaction_log.py` fail on any machine with the blob env configured (passed on the Phase 6a author's machine because they hadn't exported those vars). Observed 2026-04-17 during Phase 6a review: test run produced 443 passed / 10 failed; failing tests were reading 75 real chat entries from blob when they expected 2 from the tmp dir.
Fix: make the `tmp_data_dir` fixture (and any sibling fixture that patches config) also `monkeypatch.delenv("ENTRACLAW_BLOB_ENDPOINT", raising=False)` + same for `ENTRACLAW_BLOB_CONTAINER`. Consider a session-scoped autouse fixture that unsets blob env for *all* tests unless a test opts in. Also audit other test files that might have the same latent bug (`test_daily_summary.py`, `test_email_poll.py`, anywhere using `get_backend()`).
- **Effort:** S (~30 LOC — fixture edit + audit)
- **Source:** Phase 6a review 2026-04-17; failure is pre-existing on main, not introduced by Phase 6a

### PersonaBackend.pull_all() missing mtime-newer-local check (Phase 6d scope)
`src/entraclaw/storage/persona.py` `pull_all()` currently overwrites local files unconditionally — cloud is authoritative on pull. The persona-persistence plan §4.2 specified: "If local is newer (happens if session was offline), leave it (to be pushed next)." Phase 6a shipped without that check for the safe-starting-point framing, but it's a race-loss risk: if a session writes a memory file offline, the next online session's SessionStart pull will clobber it before the PostToolUse-Write push fires. The mitigation of this was planned for Phase 6d (ETag-based conflict resolution) but the simple mtime check should land sooner.
Fix: compare local file mtime vs blob's last-modified on pull, skip overwrite if local is newer, add to `PersonaReport` a new `skipped_local_newer` counter. Test: pytest fixture with a local file newer than the (fake) blob's content → pull_all must leave it.
- **Effort:** XS (~20 LOC + 2 tests)
- **Depends on:** Phase 6a (`1514dcd`, shipped)
- **Source:** Phase 6a review 2026-04-17; plan §4.2 said we'd do this, Phase 6a deferred

### MCP server orphans when Claude Code exits
Observed twice: when the parent Claude process exits, the `entraclaw-mcp` child keeps running. The new Claude session spawns a *second* MCP server, and both servers poll Graph independently — causing dual interaction-log writes (observed 2026-04-17: local log 54 lines vs blob log 19 lines on the same UTC day) and dual channel-push attempts. Root cause: `_background_poll_teams`, `_background_poll_email`, `_background_discover_chats`, and `_background_daily_summary` are spawned as top-level asyncio tasks inside `_initialize()`. They sit outside FastMCP's lifespan cancel scope, so when stdin closes and FastMCP's stdio read loop exits, the polling tasks keep the event loop alive and the process never terminates. Fixes in priority order: (a) spawn background tasks inside FastMCP's lifespan context manager so shutdown cancels them, (b) explicitly watch stdin for EOF in `_initialize` and cancel the task group, or (c) have polling tasks poll a shared shutdown event that FastMCP's stop hook sets. Workaround until fixed: manually `kill <pid>` old `entraclaw-mcp` processes.
- **Effort:** S (~40 LOC + test that proves stdin-EOF cancels polls)
- **Source:** Live observation 2026-04-17 (second occurrence in one day)

### Daily summary scheduler: wrong day + double-fire
Two bugs, both observed at 2026-04-17T17:00:00 PDT (= 00:00:01 UTC 2026-04-18):
1. `_run_daily_summary_internal` defaults `target_day = datetime.now(UTC).strftime("%Y-%m-%d")`. At 5pm PDT the UTC clock is already past midnight, so the scheduler summarizes the brand-new UTC day (empty) instead of the one that just ended. Fix: when called from the scheduler, target `now_utc - 1 day` — or compute the "just-ended PDT day" explicitly.
2. Scheduler fired twice at the same second — two summary emails arrived simultaneously (one for 2026-04-17, one for 2026-04-18). Suggests either a boot-time catch-up colliding with the scheduled tick or a loop that doesn't gate on "already sent today." Inspect `_background_daily_summary` for idempotency + single-fire semantics.
- **Effort:** S (~30 LOC + tests for both)
- **Source:** Live observation 2026-04-17 evening (first real scheduled fire)

### Email cursor sub-second precision
`email_poll.poll_once` returns `latest_ts` verbatim from Graph; the cursor file may end up at second precision while Graph internally compares with sub-second. Result: an email at the cursor's exact second gets re-returned every poll. Per-session dedup in `_background_poll_email` handles within-session, but the email re-pushes once on every server restart. Real fix: bump cursor by 1ms when it equals the latest receivedDateTime, or store sub-second precision unconditionally.
- **Effort:** XS (~10 LOC + 1 test)
- **Source:** Live observation 2026-04-17 (Jack Test "Ball game tonight" loop)

### ~~Token auto-refresh in teams_send~~ ✅ DONE
Implemented as `_with_token_retry()` in `mcp_server.py` and `_ensure_valid_token()` (proactive refresh at 55 min). All tools use it.

### AppContainer sandbox production implementation
Tonight's spike proves feasibility. Production version needs: filesystem allowlist, network filtering (Graph API only), process spawn restrictions, MCP server integration. May require Win32 C extension from Python.
- **Effort:** L (CC: ~1-2 days)
- **Depends on:** AppContainer spike results
- **Source:** CEO review, refined premise (sandbox co-equal with identity)

## P2

### Move provisioner to standalone service for production
Extract the background provisioner from the MCP server process into a separate service that handles Agent User creation server-side. Shipping `Application.ReadWrite.All` client_credentials to end-user machines is a trust boundary issue for production. Embedded provisioner is acceptable for research (single developer machine).
- **Effort:** L (CC: ~M)
- **Depends on:** PR #2 (embedded provisioner ships first as proof of concept)
- **Source:** CEO review + Codex cross-model review, tension point #2

### ~~Graph API 429 rate limit handler~~ ✅ DONE
Implemented as `RetryOn429Transport` in `tools/rate_limit.py`. Wraps httpx async transport — all Graph calls (send, read, create_or_find_chat) auto-retry up to 3 times with Retry-After backoff. 7 tests.

### Persist sent-message IDs across restarts
Serialize the in-memory sent-message-ID set to keyring or local file, reload on startup. Currently the set is lost on restart, meaning prior agent-sent messages in delegated mode could be re-processed as human instructions. The `[EntraClaw]` prefix provides a secondary defense (filter messages starting with prefix after restart), but persistence eliminates the gap entirely. ~50 LOC + corruption handling.
- **Effort:** S (CC: ~S)
- **Depends on:** PR #1 (sent-message tracking must ship first)
- **Source:** Eng review + Codex outside voice, tension point #3

## P3

### Unify HTTP stacks (MSAL requests → httpx adapter)
Replace MSAL's default `requests` HTTP backend with an httpx adapter via `msal-extensions`, so the project uses a single HTTP library. Two HTTP libraries in one process increases attack surface and dependency weight.
- **Effort:** S (CC: ~S)
- **Depends on:** PR #1 (MSAL integration must ship first)
- **Source:** CEO review Section 10, technical debt item #1

### Tenant-scoped runtime state for true multi-user support
Add per-tenant scoping for watched_chats, token cache keys, and data directories. Currently acceptable because each Claude Code session spawns its own MCP server process (per-process model). Future scaling may require shared-process support.
- **Effort:** M (CC: ~S)
- **Depends on:** PR #1
- **Source:** CEO review + Codex cross-model review, tension point #4

### Multi-account identity selection (login_hint)
Pass `login_hint` from persisted `IdentitySession` to MSAL `acquire_token_interactive()` on restart, so users with multiple Entra accounts don't get re-prompted. Currently MSAL picks the most recent account, which works for single-account research.
- **Effort:** S (CC: ~S)
- **Depends on:** PR #1 (IdentitySession dataclass + MSAL integration)
- **Source:** Eng review + Codex outside voice, tension point #6

### Restart-after-provisioning as live-swap fallback
If live token swap (PR #2) proves too flaky in practice, implement a restart path: provisioner completes → writes creds to keyring → signals MCP to restart → fast path picks up AGENT_USER on next boot. Insurance policy for the live swap design.
- **Effort:** S (CC: ~S)
- **Depends on:** PR #2 (provisioner + live swap must ship first)
- **Source:** Eng review + Codex outside voice, tension point #5
