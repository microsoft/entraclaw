# TODOS

## P1

### Token auto-refresh in teams_send
When Graph API returns 401, silently call `openclaw_refresh` and retry once before failing. Without this, the demo breaks after 60-90 minutes (token expiry). Requires implementing `openclaw_refresh` as tool #4.
- **Effort:** S (CC: ~15 min)
- **Depends on:** `tools/identity.py` openclaw_refresh tool
- **Source:** CEO review, Section 2 (Error Map)

### AppContainer sandbox production implementation
Tonight's spike proves feasibility. Production version needs: filesystem allowlist, network filtering (Graph API only), process spawn restrictions, MCP server integration. May require Win32 C extension from Python.
- **Effort:** L (CC: ~1-2 days)
- **Depends on:** AppContainer spike results
- **Source:** CEO review, refined premise (sandbox co-equal with identity)

## P2

### Graph API 429 rate limit handler
Parse `Retry-After` header, wait, retry. Implement as httpx middleware so it applies to all Graph calls. Teams rate limits: ~10 messages/10s per thread.
- **Effort:** S (CC: ~15 min)
- **Depends on:** `tools/teams.py` exists
- **Source:** CEO review, Section 2 (Error Map)
