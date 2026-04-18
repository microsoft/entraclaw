"""Tests for scripts/provision_blob_storage.py (ADR-005, Phase 5).

The script orchestrates ``az`` CLI calls. We mock ``subprocess.run`` and
verify (a) the deterministic name helpers, (b) the right ``az`` commands
get issued in the right order, (c) idempotency — i.e. ``show`` succeeds
short-circuits ``create``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Load the script as a module without packaging it
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "provision_blob_storage.py"
spec = importlib.util.spec_from_file_location("provision_blob_storage", _SCRIPT)
provision_blob_storage = importlib.util.module_from_spec(spec)
sys.modules["provision_blob_storage"] = provision_blob_storage
assert spec.loader is not None
spec.loader.exec_module(provision_blob_storage)


def _ok(stdout: str = "") -> MagicMock:
    return MagicMock(returncode=0, stdout=stdout, stderr="")


def _err(stderr: str = "boom", returncode: int = 1) -> MagicMock:
    return MagicMock(returncode=returncode, stdout="", stderr=stderr)


class TestNameHelpers:
    def test_storage_account_name_is_deterministic(self) -> None:
        a = provision_blob_storage.storage_account_name_for_tenant("tid-123")
        b = provision_blob_storage.storage_account_name_for_tenant("tid-123")
        assert a == b

    def test_storage_account_name_is_lowercase_alnum_within_24(self) -> None:
        name = provision_blob_storage.storage_account_name_for_tenant("tid-123")
        assert 3 <= len(name) <= 24
        assert name == name.lower()
        assert name.isalnum()

    def test_storage_account_name_differs_per_tenant(self) -> None:
        a = provision_blob_storage.storage_account_name_for_tenant("tid-1")
        b = provision_blob_storage.storage_account_name_for_tenant("tid-2")
        assert a != b

    def test_container_name_for_agent_user(self) -> None:
        oid = "ABCD-1234-5678-90AB"
        name = provision_blob_storage.container_name_for_agent_user(oid)
        assert name.startswith("agent-")
        assert name == name.lower()


class TestEndToEndProvisionAllNew:
    """Resource group, storage account, container all need creating."""

    def test_creates_in_order_and_assigns_rbac(self) -> None:
        results = [
            _err("not found"),  # group show
            _ok(),              # group create
            _err("not found"),  # account show
            _ok(),              # account create
            _err("not found"),  # container show
            _ok(),              # container create
            _ok("/subscriptions/sub/resourceGroups/entraclaw-rg/providers/Microsoft.Storage/storageAccounts/acct"),  # noqa: E501
            _ok(),              # role assignment create
        ]
        with patch.object(provision_blob_storage, "_run_az", side_effect=results) as m:
            endpoint, container = provision_blob_storage.provision(
                tenant_id="tid-123",
                agent_user_object_id="oid-abc",
            )

        assert endpoint.startswith("https://")
        assert endpoint.endswith(".blob.core.windows.net")
        assert container.startswith("agent-")

        all_calls = [c.args[0] for c in m.call_args_list]
        assert any(args[:3] == ["group", "create", "--name"] for args in all_calls)
        assert any(args[:3] == ["storage", "account", "create"] for args in all_calls)
        assert any(args[:3] == ["storage", "container", "create"] for args in all_calls)
        assert any(args[:3] == ["role", "assignment", "create"] for args in all_calls)

    def test_idempotent_when_everything_exists(self) -> None:
        results = [
            _ok(),  # group show
            _ok(),  # account show
            _ok(),  # container show
            _ok("/subscriptions/sub/resourceGroups/entraclaw-rg/providers/Microsoft.Storage/storageAccounts/acct"),  # noqa: E501
            _ok(),  # role assignment create (idempotent itself)
        ]
        with patch.object(provision_blob_storage, "_run_az", side_effect=results) as m:
            provision_blob_storage.provision(
                tenant_id="tid-123",
                agent_user_object_id="oid-abc",
            )
        all_calls = [c.args[0] for c in m.call_args_list]
        assert not any(args[:3] == ["group", "create", "--name"] for args in all_calls)
        assert not any(args[:3] == ["storage", "account", "create"] for args in all_calls)
        assert not any(args[:3] == ["storage", "container", "create"] for args in all_calls)


class TestRoleAssignmentBenignErrors:
    def test_already_exists_treated_as_success(self) -> None:
        results = [
            _ok(),  # group show
            _ok(),  # account show
            _ok(),  # container show
            _ok("/subscriptions/.../accounts/x"),  # show -o tsv
            _err("RoleAssignmentExists: ..."),  # role assignment create
        ]
        with patch.object(provision_blob_storage, "_run_az", side_effect=results):
            # Should NOT raise
            provision_blob_storage.provision(
                tenant_id="tid-123", agent_user_object_id="oid-abc"
            )


class TestFailures:
    def test_group_create_failure_raises_runtime_error(self) -> None:
        results = [_err("not found"), _err("auth blocked")]
        with (
            patch.object(provision_blob_storage, "_run_az", side_effect=results),
            pytest.raises(RuntimeError, match="az group create failed"),
        ):
            provision_blob_storage.provision(
                tenant_id="tid-123", agent_user_object_id="oid-abc"
            )


class TestMain:
    def test_main_prints_kv_lines_on_success(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(
            provision_blob_storage,
            "provision",
            return_value=("https://acct.blob.core.windows.net", "agent-oid"),
        ):
            rc = provision_blob_storage.main(
                ["--tenant-id", "tid", "--agent-user-object-id", "oid"]
            )
        assert rc == 0
        out = capsys.readouterr().out.splitlines()
        assert "BLOB_ENDPOINT=https://acct.blob.core.windows.net" in out
        assert "BLOB_CONTAINER=agent-oid" in out

    def test_main_returns_nonzero_on_failure(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(
            provision_blob_storage,
            "provision",
            side_effect=RuntimeError("nope"),
        ):
            rc = provision_blob_storage.main(
                ["--tenant-id", "tid", "--agent-user-object-id", "oid"]
            )
        assert rc == 1
