# TODOS

## P1

### ~~Token auto-refresh in teams_send~~ ✅ DONE
Implemented as `_with_token_retry()` in `mcp_server.py` and `_ensure_valid_token()` (proactive refresh at 55 min). All tools use it.

### AppContainer sandbox production implementation
Tonight's spike proves feasibility. Production version needs: filesystem allowlist, network filtering (Graph API only), process spawn restrictions, MCP server integration. May require Win32 C extension from Python.
- **Effort:** L (CC: ~1-2 days)
- **Depends on:** AppContainer spike results
- **Source:** CEO review, refined premise (sandbox co-equal with identity)

## P2

### ~~Graph API 429 rate limit handler~~ ✅ DONE
Implemented as `RetryOn429Transport` in `tools/rate_limit.py`. Wraps httpx async transport — all Graph calls (send, read, create_or_find_chat) auto-retry up to 3 times with Retry-After backoff. 7 tests.
