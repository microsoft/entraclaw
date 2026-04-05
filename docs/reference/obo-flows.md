# OBO Token Flows Reference

## Overview

On-Behalf-Of (OBO) is the core auth pattern for Openclaw. It lets an agent act with the user's permissions while being **identified as the agent** in all logs.

## MSAL OBO Exchange

```python
from msal import ConfidentialClientApplication

app = ConfidentialClientApplication(
    client_id=AGENT_CLIENT_ID,
    client_credential=AGENT_SECRET,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
)

result = app.acquire_token_on_behalf_of(
    user_assertion=human_access_token,
    scopes=["https://graph.microsoft.com/.default"],
)
```

## Token Claims

The OBO token contains:

| Claim | Value | Purpose |
|-------|-------|---------|
| `sub` | Agent's object ID | Identifies the agent, not the human |
| `oid` | Agent's object ID | Same — agent is the principal |
| `azp` | Agent's client ID | The app registration for the agent |
| `obo_claim` | Human's object ID | Links back to the consenting human |

## Consent Scopes

The agent should request the minimum scopes needed for its task. Common scopes:

- `User.Read` — read the consenting user's profile
- `Files.ReadWrite` — access files on behalf of the user
- `Chat.ReadWrite` — send/receive Teams messages
- `AuditLog.Read.All` — read audit logs (if the agent self-monitors)

## Token Lifecycle

1. **Acquisition**: OBO exchange returns an access token (1 hour) + refresh token
2. **Refresh**: MSAL handles silent refresh automatically via token cache
3. **Expiry**: If refresh fails, re-prompt the human for consent
4. **Revocation**: Human can revoke consent at any time via Entra portal

## Error Handling

| Error | Cause | Recovery |
|-------|-------|----------|
| `AADSTS50013` | Assertion (human token) expired | Re-authenticate the human |
| `AADSTS65001` | User hasn't consented to scopes | Trigger consent prompt |
| `AADSTS700024` | Client assertion invalid | Check agent credential/secret |
