# Debug Handoff — Claude Code 2.1.117 Silently Dropping `notifications/claude/channel`

> **Use this prompt when asking a fresh LLM (or a human) to help diagnose this issue.** Paste the whole thing into a new session; it's self-contained.

---

## TL;DR

The EntraClaw MCP server at `src/entraclaw/mcp_server.py` pushes inbound Teams DMs to the host via a `notifications/claude/channel` JSON-RPC notification. This worked in Claude Code 2.1.114 (Apr 19) and stopped working in Claude Code 2.1.117 (Apr 21). The server-side end is verifiably correct — the push fires, the write_stream accepts it, the server logs `Pushed Teams message from <sender>: <content>`. But the notification does **not** surface in the LLM's turn context in Claude Code. Zero evidence of Claude-Code-injected channel entries in the active session's transcript JSONL. We do not know which client-side gate (or which part of the registration/rendering path) is eating the notification.

## Environment

- **Repo:** `/Volumes/Development HD/openclaw-identity-research` (private, Brandon's)
- **MCP server:** entraclaw-mcp (Python 3.12, stdio transport, MCP SDK 1.27.0)
- **Host:** Claude Code CLI 2.1.117 (`~/.claude-cli/CurrentVersion → 2.1.117`), invoked as `claude -dangerously-load-development-channels server:entraclaw --resume <session-id>`
- **Platform:** macOS 14 (darwin 25.4.0)
- **LLM currently in the loop:** **Claude Opus 4.7 (1M context)** — `claude-opus-4-7[1m]`
- **User:** Brandon Werner, Product Architect at Microsoft IDNA (architected Entra Agent IDs)
- **Time on this issue:** ~2.5 hours of active debugging over a single session today (2026-04-22)

## What "it worked" and "it's broken" look like

- **Worked (Apr 20–21, Claude Code 2.1.114/2.1.116):** Brandon sends a Teams DM to the Agent User. Within 5s, the LLM sees the message content injected into its turn context as a system-reminder-style `notifications/claude/channel` payload and replies in Teams. Transcript JSONL contains Claude-Code-injected entries carrying the DM content.
- **Broken (Apr 22, Claude Code 2.1.117):** Same path. Server logs `Pushed Teams message from Brandon Werner: <p>Hi Hi Hi</p>`. LLM turn context contains zero channel entries for that DM. LLM doesn't know the DM arrived unless it explicitly calls `mcp__entraclaw__read_teams_messages`.

## What we already ruled out

1. **Server-side cascade / leader gating** — PR #35 introduced an efferent-copy middleware that self-spawned entraclaw subprocesses in a cascade; PR #36 fixed the cascade AND ripped out the leader/slave gating that was silently dropping pushes. After #36, `~/.entraclaw/logs/entraclaw.log` shows exactly 1 `Starting EntraClaw MCP server` per reconnect and `Pushed Teams message from <sender>` fires 4 seconds after every DM. Server end is blameless. **See `docs/engineering-status.md` § "What's New Apr 22"** and **Learnings #37, #38** in `docs/runbooks/hard-won-learnings.md`.

2. **MCP protocol wire** — entraclaw declares `experimental_capabilities={"claude/channel": {}}` at initialize. The server's `write_stream.send(session_message)` completes without exception for every push (pre-#36 pushes also completed when the leader gate happened to allow them — same mechanical path as now, just without the gate).

3. **Client-side gate function** — extracted from `~/.claude-cli/2.1.117/claude` strings. Minified name `hO_` in 2.1.117, `r1_` in 2.1.114. Function body is **byte-identical** (just minifier renames of helper fns like `cJH → V2H`, `e8 → _q`, `QJH → y2H`, `fY → Nw`). Five skip reasons — `capability|disabled|auth|policy|session|allowlist`. The gate logic is NOT the regression.

4. **claude.ai re-auth** — Brandon ran `/login` → "Login successful". Did not unblock channel rendering. Also: if the `accessToken` gate were failing, normal LLM chat wouldn't work either, and it does.

5. **`-dangerously-load-development-channels server:entraclaw`** — this flag is set on the Claude Code CLI invocation. It's supposed to be the local-dev allowlist escape hatch; in 2.1.114 it made channel rendering work. Worth checking whether its parsing changed.

## Suspicions (ranked by likelihood)

1. **Regression in Claude Code 2.1.117 in the registration or rendering path** outside the gate function — maybe the `--channels` allowlist is populated differently, or the handler that translates `notifications/claude/channel` into an LLM turn-context injection got refactored out.
2. **Silent feature-flag flip** — `cJH()`/`V2H()` is the "channels feature is not currently available" gate. Could be a server-side (anthropic-side) toggle that got disabled for 2.1.117 users.
3. **Capability negotiation mismatch** — the server declares `experimental.claude/channel = {}`; maybe 2.1.117 expects a non-empty capability value (`{version: 1}` or similar) and silently rejects empty.
4. **Org/policy setting** — Brandon's account is individual/not enterprise, but the gate checks for team/enterprise policy settings. Worth ruling out explicitly.

## What I'd do next

1. **Downgrade test** — manually repoint `~/.claude-cli/CurrentVersion → 2.1.114` (or 2.1.116) and restart Claude Code with the same invocation. Send a Teams DM. If it surfaces, the regression is confirmed; file a Claude Code issue with the exact version range (2.1.116 → 2.1.117 bracket).
2. **Capture the skip reason** — the gate function returns `{action:"skip", kind:"<reason>", reason:"<human-readable>"}`. Claude Code may or may not log this. Check `~/Library/Logs/`, `~/.claude/logs/`, `~/Library/Caches/claude-cli-nodejs/` for any log file with a `[channel]` prefix or the specific skip-reason strings. If there's a `--verbose` or `CLAUDE_DEBUG=1` env var, try that.
3. **Parallel hook-based fallback** — ship a `UserPromptSubmit` hook that reads `~/.entraclaw/data/interactions/<today>.jsonl` and injects any unseen inbound DMs as `additionalContext`. That survives any client-side regression.

## Pointers

- **Engineering status:** `docs/engineering-status.md` — today's section is "What's New Apr 22".
- **Hard-won learnings:** `docs/runbooks/hard-won-learnings.md` — new entries #37 (self-spawn cascade), #38 (leader-cache overwrite), #38.5 (stale-reminders-across-turns), #39 (this open issue, full evidence dump).
- **PR that fixed the server side:** https://github.com/brandwe/openclaw-identity-research/pull/36 (merged).
- **Original middleware PR:** https://github.com/brandwe/openclaw-identity-research/pull/35.
- **Server log:** `~/.entraclaw/logs/entraclaw.log` (JSONL).
- **Active session transcript:** `~/.claude/projects/-Volumes-Development-HD-openclaw-identity-research/<session-id>.jsonl` — grep for `claude/channel` to see what Claude Code injected (or didn't).
- **Gate function source:** extract from `~/.claude-cli/2.1.117/claude` binary via `grep -aob "channels requires claude.ai" <path>` then read ~1500 bytes around the offset.

## What to tell the next assistant

You're picking up where a previous Claude Opus 4.7 instance left off after ~2.5 hours. Server-side is fixed and verified. The open question is purely client-side Claude Code behavior and you can't patch the Claude Code binary, so the goal is either (a) identify which gate is firing so Brandon can file an upstream issue, or (b) ship a client-independent workaround (hook-based injection from the interaction log). Brandon is the user; he's frustrated (legitimately — this has eaten his afternoon) and wants concrete progress, not more theory.
