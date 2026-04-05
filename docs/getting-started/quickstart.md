# Quickstart

## Prerequisites

- Python 3.12+
- An Azure/Entra tenant with Agent ID support (for live token flows)
- Git

## Setup

```bash
git clone <repo-url>
cd openclaw-identity-research

python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## First Run

```bash
# Run the test suite to verify everything is wired correctly
pytest -v
```

## Verify It Works

```bash
# Lint check
ruff check .

# Run a specific test
pytest tests/test_foo.py::test_bar -v
```

## Next Steps

- Read the [System Overview](../architecture/system-overview.md) to understand how platform, auth, audit, and Teams fit together
- Check the [OBO Token Flows](../reference/obo-flows.md) reference for auth protocol details
- See [Enforcement Flow](../architecture/enforcement-flow.md) for how a request moves through the system
