# Openclaw Identity Research

Openclaw brings cloud-style identity tracking to device-local agents. When an autonomous agent runs on your Mac, Linux, or Windows machine, it gets its own **Agent ID** and uses **on-behalf-of (OBO)** token flows — so audit logs always distinguish agent actions from human actions.

## Key Concepts

| Concept | What It Does |
|---------|-------------|
| **Agent ID** | A distinct identity for an autonomous agent, separate from the human user |
| **OBO Flow** | Token exchange where the human consents and the agent gets an attributed token |
| **Platform Abstraction** | OS-specific agent identity lifecycle (create, consent, acquire token, audit) |
| **Digital Worker** | The agent's identity as seen in sign-in/access logs |
| **Teams Agent User** | Bidirectional Teams channel — agent messages human, human steers agent |

## Where to Start

- **New to the project?** Start with the [Quickstart](getting-started/quickstart.md)
- **Understanding the design?** Read [System Overview](architecture/system-overview.md)
- **How tokens flow?** See [OBO Token Flows](reference/obo-flows.md)
- **Debugging?** Check [Hard-Won Learnings](runbooks/hard-won-learnings.md)
- **Why we made a decision?** Browse [Architecture Decision Records](decisions/README.md)

## Open Research Questions

- What identity system replaces Live ID for agent-to-Teams auth at scale?
- How do you track agent actions across OSes with a universal audit store?
- Teams Graph API coverage: what's missing vs. the Teams UX?
