# Hard-Won Learnings

Append-only log of gotchas, surprises, and non-obvious behaviors discovered during development and operations. Never delete entries — mark obsolete ones as `[HISTORICAL]`.

## Active Learnings

### Learning #1: Azure CLI Tokens Rejected by Agent Identity APIs

**Date:** 2026-04-06
**Context:** Running setup.sh to create Agent Identity Blueprint
**Problem:** `az rest` calls to Agent Identity beta APIs returned 403
**Root cause:** Azure CLI tokens always include `Directory.AccessAsUser.All` delegated permission. Agent Identity APIs explicitly reject any token containing this permission.
**Fix:** Created a dedicated "Openclaw Provisioner" app registration. Use `ClientSecretCredential` from `azure-identity` to get a clean `client_credentials` token.
**Prevention:** Never use `az rest` or `DefaultAzureCredential` for Agent Identity APIs. Always use a dedicated app with `client_credentials`.

### Learning #2: BlueprintPrincipal Must Be Created Separately

**Date:** 2026-04-06
**Context:** Creating Agent Identity after Blueprint
**Problem:** Agent Identity creation failed with 400: "The Agent Blueprint Principal for the Agent Blueprint does not exist"
**Root cause:** Creating a Blueprint (`POST /applications`) does NOT auto-create its BlueprintPrincipal (service principal). This is an explicit second step.
**Fix:** Always `POST /servicePrincipals` with `@odata.type: AgentIdentityBlueprintPrincipal` immediately after Blueprint creation. Also check on the skip path (idempotent re-runs).
**Prevention:** Follow the implement-agent-id skill checklist.

### Learning #3: Token Responses Return Error Dicts, Not Exceptions

**Date:** 2026-04-06
**Context:** Token exchange returning errors
**Problem:** Accessing `result["access_token"]` threw KeyError with no context
**Root cause:** Entra token endpoint returns `{"error": "...", "error_description": "..."}` on failure as JSON, not HTTP errors. This is the OAuth2 convention.
**Fix:** Check every token response: `if "error" in data: raise TokenExchangeError(...)`.
**Prevention:** Never access `access_token` without checking for `error` key first.

### Learning #5: Agent IDs Cannot Have Password Credentials

**Date:** 2026-04-06
**Context:** Trying to create an agent as a regular Entra user with a password
**Problem:** Agent Identities are service principals without backing application objects. `passwordCredentials` returns `PropertyNotCompatibleWithAgentIdentity`.
**Root cause:** Agent IDs are designed for managed identity federation and certificates, not passwords.
**Fix:** Use client credentials on the Blueprint (which IS an application) for device-local scenarios. Production uses managed identity + federated credentials.
**Prevention:** Never create "fake users" for agents. Always use the Agent Identity Blueprint → Agent Identity pattern.

### Learning #6: Never Redirect Stderr to /dev/null

**Date:** 2026-04-06
**Context:** Admin consent failure was invisible, token acquisition failure was invisible
**Problem:** `2>/dev/null` hid the actual error messages, turning specific failures into generic "something failed" messages
**Root cause:** Copy-pasted shell patterns from examples that prioritize clean output over debuggability
**Fix:** Removed all instances of `2>/dev/null` from scripts. Guard `source .env` with `[ -f .env ]` instead.
**Prevention:** Never swallow stderr. Errors must always be visible.

### Learning #7: az CLI JSON Output Safer Than TSV

**Date:** 2026-04-06
**Context:** `az ad app credential reset --query password -o tsv` included Azure CLI WARNING text
**Problem:** The extracted password was corrupted by a WARNING message about protecting credentials
**Root cause:** `-o tsv` outputs to stdout, but Azure CLI also writes warnings to stdout (not stderr) in some cases
**Fix:** Parse full JSON output with Python: `json.loads(output)['password']`
**Prevention:** Use `-o json` and parse with Python/jq, not `-o tsv`.

### Learning #8: Permission Propagation Takes 30-120 Seconds

**Date:** 2026-04-06
**Context:** Token acquisition after admin consent returned cached claims without new permissions
**Problem:** Immediate token acquisition after consent got a token without Agent Identity permissions
**Root cause:** Entra's token endpoint serves cached claims for 30-120s after permission changes.
**Fix:** 10-40s retry backoff + 30s explicit wait after consent.
**Prevention:** Always add propagation delay after permission changes.

### Learning #9: Agent User UPN Must Use a Verified Domain

**Date:** 2026-04-06
**Context:** Creating Agent User via `POST /beta/users` with `@odata.type: microsoft.graph.agentUser`
**Problem:** 400: "The root domain of the specified UPN does not belong to a verified domain"
**Root cause:** `az account show` has no `tenantDefaultDomain` field. Code fell back to `{tenant-id}.onmicrosoft.com` which is not a verified domain.
**Fix:** Extract the domain from the signed-in user's UPN via `az ad signed-in-user show --query userPrincipalName`. That domain is always verified.
**Prevention:** Never construct UPN domains from tenant IDs. Always derive from an existing verified UPN.

### Learning #10: oAuth2PermissionGrant Requires startTime

**Date:** 2026-04-06
**Context:** Creating consent grant for Agent User to use Graph Chat/Teams permissions
**Problem:** 400: "Missing property: startTime"
**Root cause:** The Graph API now requires a `startTime` field on `oAuth2PermissionGrant` creation. This wasn't required in older API versions and isn't mentioned in most examples.
**Fix:** Add `"startTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")` to the request body.
**Prevention:** Always include `startTime` in `oAuth2PermissionGrant` creation.

### Learning #11: Provisioner Needs DelegatedPermissionGrant.ReadWrite.All for Consent

**Date:** 2026-04-06
**Context:** Creating `oAuth2PermissionGrant` for Agent User → Graph permissions
**Problem:** 403: "Insufficient privileges to complete the operation"
**Root cause:** The provisioner app had Agent Identity and Application permissions but lacked `DelegatedPermissionGrant.ReadWrite.All` — needed to create delegated permission grants on behalf of the Agent User.
**Fix:** Added `DelegatedPermissionGrant.ReadWrite.All` and `User.ReadWrite.All` to `BASE_PERMISSION_VALUES` in `entra_provisioning.py`.
**Prevention:** The provisioner needs permissions for everything it does: Blueprint CRUD, Agent Identity CRUD, Agent User CRUD, license assignment, AND consent grants. All are in `BASE_PERMISSION_VALUES` + dynamic `AgentIdentity`/`AgentIdUser` discovery.

### Learning #12: Three-Hop Flow Requires fmi_path Parameter

**Date:** 2026-04-06
**Context:** Hop 2 of the three-hop Agent User flow failing with AADSTS700211
**Problem:** "No matching federated identity record found for presented assertion issuer"
**Root cause:** Hop 1 was requesting `scope=https://graph.microsoft.com/.default` (a Graph resource token) instead of `scope=api://AzureADTokenExchange/.default` (a token exchange token). It also lacked the `fmi_path` parameter that tells Entra which Agent Identity this token is for.
**Fix:** Hop 1: `scope=api://AzureADTokenExchange/.default`, `fmi_path={agent-identity-id}`. Hop 3: add `requested_token_use=on_behalf_of`.
**Prevention:** Follow the exact protocol from the Microsoft docs: "Agent's user account impersonation protocol". The `fmi_path` parameter is essential and non-obvious.

### Learning #13: Existing Non-Teams Licenses Don't Count

**Date:** 2026-04-06
**Context:** License assignment step skipping because Agent User already had a license
**Problem:** Agent User had Azure AD Premium P1 inherited from an "All Users" group, but P1 doesn't include Teams. The license check saw "has 1 license" and skipped.
**Root cause:** Checking `len(assignedLicenses) > 0` instead of checking whether any license is Teams-capable.
**Fix:** Resolve SKU IDs to part numbers and check against `TEAMS_CAPABLE_SKUS` list.
**Prevention:** Always check license capabilities, not just presence.

### Learning #14: MCP Tool Names Must Match User Intent

**Date:** 2026-04-06
**Context:** LLM client not calling `openclaw_teams_send` when user said "message brandon"
**Problem:** The LLM read the tool descriptions but didn't connect "message brandon@werner.ac" with a tool named `openclaw_teams_send`
**Root cause:** Namespaced tool names (`openclaw_teams_send`) are jargon. The LLM looks for intent matches, not namespace patterns.
**Fix:** Renamed to `send_teams_message`, `read_teams_messages`, `whoami`, `audit_log`. Added trigger phrases to descriptions: "message", "notify", "tell", "ping", "contact". Added FastMCP `instructions` field with intent→tool mapping.
**Prevention:** Name tools as verbs the user would say. Pack descriptions with synonyms.

---

## Historical Learnings

### [HISTORICAL] Learning #4: OBO Requires Matching Token Audience

**Date:** 2026-04-06
**Superseded by:** Agent User three-hop flow (ADR-002). OBO is no longer used.
**Original context:** Device code flow with `scopes=["User.Read"]` produces token with `aud=https://graph.microsoft.com`. OBO exchange requires matching audience. Fix was to expose custom API scope `api://<client-id>/access_as_user`.
