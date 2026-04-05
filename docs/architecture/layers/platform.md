# Platform Abstraction Layer

## Purpose

Provides a uniform interface for agent identity operations across macOS, Linux, and Windows. Each OS has different mechanisms for process identity, credential storage, and user consent — this layer abstracts them behind `AgentIdentityProvider`.

## Interface

```python
class AgentIdentityProvider(Protocol):
    def create_agent_id(self) -> AgentIdentity: ...
    def store_credential(self, agent_id: str, credential: bytes) -> None: ...
    def retrieve_credential(self, agent_id: str) -> bytes: ...
    def request_user_consent(self, agent_id: str, scopes: list[str]) -> ConsentResult: ...
```

## OS-Specific Considerations

| OS | Credential Storage | Consent UX | Process Isolation |
|----|-------------------|------------|-------------------|
| macOS | Keychain Services | System dialog | App sandbox / launchd |
| Linux | Secret Service (D-Bus) / keyring | Terminal prompt (TBD) | systemd user units |
| Windows | Credential Manager / DPAPI | UAC-style dialog | Windows service / task scheduler |

## Runtime Dispatch

```python
import platform

def get_provider() -> AgentIdentityProvider:
    system = platform.system()
    if system == "Darwin":
        from .mac import MacIdentityProvider
        return MacIdentityProvider()
    elif system == "Linux":
        from .linux import LinuxIdentityProvider
        return LinuxIdentityProvider()
    elif system == "Windows":
        from .windows import WindowsIdentityProvider
        return WindowsIdentityProvider()
    raise UnsupportedPlatformError(system)
```
