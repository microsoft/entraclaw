"""Windows credential store backed by Credential Locker + Cert: store lookup.

Two responsibilities:

1. Generic key-value secrets via ``keyring`` (maps to Windows Credential
   Manager). This covers refresh tokens, MSAL cache markers, and any
   other small string secret. Identical contract to the Mac/Linux
   implementations.
2. ``find_cert_by_thumbprint`` — query ``Cert:\\CurrentUser\\My`` for a
   cert by SHA-1 hex thumbprint. Used by preflight checks and rotation
   helpers to confirm the Blueprint cert is still present without
   exporting the private key (which is non-exportable on the CNG path).

Unlike the Mac path, there is no ``blueprint-private-key`` PEM entry —
the Blueprint private key lives in CNG and never leaves it. ``cncrypt_signer``
performs the actual signing operation.
"""

from __future__ import annotations

import contextlib
import ctypes
import re
import sys
from typing import Any

import keyring
import keyring.errors

_THUMBPRINT_RE = re.compile(r"^[0-9A-Fa-f]{40}$")

CERT_STORE_PROV_SYSTEM_W = 10
CERT_SYSTEM_STORE_CURRENT_USER = 1 << 16
CERT_FIND_HASH = 0x10000


class _CryptIntegerBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _load_crypt32() -> Any:
    """Return the crypt32 DLL handle. Windows-only."""
    if sys.platform != "win32":
        raise RuntimeError(
            "platform.windows cert lookup requires Windows; got platform=" + sys.platform
        )
    return ctypes.windll.crypt32  # pragma: no cover


class WindowsCredentialStore:
    """Credential Locker for KV secrets + Cert: store query for thumbprints."""

    def store(self, service: str, key: str, value: str) -> None:
        keyring.set_password(service, key, value)

    def retrieve(self, service: str, key: str) -> str | None:
        return keyring.get_password(service, key)

    def delete(self, service: str, key: str) -> None:
        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(service, key)

    def find_cert_by_thumbprint(self, thumbprint: str) -> bool:
        """Return True iff a cert with this SHA-1 thumbprint exists in
        ``Cert:\\CurrentUser\\My``.

        Args:
            thumbprint: 40-char hex SHA-1 thumbprint.
        """
        if not _THUMBPRINT_RE.match(thumbprint or ""):
            raise ValueError(f"thumbprint must be 40 hex chars, got: {thumbprint!r}")

        crypt32 = _load_crypt32()
        store = crypt32.CertOpenStore(
            CERT_STORE_PROV_SYSTEM_W,
            0,
            0,
            CERT_SYSTEM_STORE_CURRENT_USER,
            ctypes.c_wchar_p("My"),
        )
        if not store:
            raise RuntimeError("CertOpenStore(CurrentUser\\My) failed")

        cert_ctx = 0
        try:
            raw = bytes.fromhex(thumbprint)
            buf = (ctypes.c_ubyte * len(raw))(*raw)
            blob = _CryptIntegerBlob(cbData=len(raw), pbData=buf)
            cert_ctx = crypt32.CertFindCertificateInStore(
                store, 0x00010001, 0, CERT_FIND_HASH, ctypes.byref(blob), None
            )
            return bool(cert_ctx)
        finally:
            if cert_ctx:
                crypt32.CertFreeCertificateContext(cert_ctx)
            crypt32.CertCloseStore(store, 0)
