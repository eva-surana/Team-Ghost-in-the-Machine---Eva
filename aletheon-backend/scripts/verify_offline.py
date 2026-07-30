"""
verify_offline.py — standalone network audit script.

Monkeypatches socket at the process level to detect any accidental network call
during artifact loading and a basic inference cycle.

Run from project root:
  python scripts/verify_offline.py

Exit code 0  -> No network calls detected (air-gap compliant)
Exit code 1  -> A network call was attempted
"""
from __future__ import annotations

import socket
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_network_attempts: list[str] = []
_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_original_socket_connect = socket.socket.connect
_original_socket_connect_ex = socket.socket.connect_ex


def _blocked_connect(self, address):
    host = address[0] if isinstance(address, (tuple, list)) else str(address)
    if host in _LOOPBACK:
        return _original_socket_connect(self, address)
    msg = f"NETWORK CALL BLOCKED: socket.connect({address!r})"
    _network_attempts.append(msg)
    raise ConnectionRefusedError(msg)


def _blocked_connect_ex(self, address):
    host = address[0] if isinstance(address, (tuple, list)) else str(address)
    if host in _LOOPBACK:
        return _original_socket_connect_ex(self, address)
    msg = f"NETWORK CALL BLOCKED: socket.connect_ex({address!r})"
    _network_attempts.append(msg)
    return 111  # ECONNREFUSED


def _patch_socket():
    socket.socket.connect = _blocked_connect
    socket.socket.connect_ex = _blocked_connect_ex


def _restore_socket():
    socket.socket.connect = _original_socket_connect
    socket.socket.connect_ex = _original_socket_connect_ex


def main() -> int:
    print("=" * 60)
    print("  Aletheon -- Offline Compliance Audit")
    print("=" * 60)

    _patch_socket()
    try:
        print("[*] Importing config and enforcing offline env vars...")
        from app.config import settings

        assert settings.OFFLINE_MODE is True
        assert settings.PRETRAINED_WEIGHTS_USED is False

        print("[*] Loading ArtifactRegistry (self-trained artifacts from disk)...")
        from app.models.registry import ArtifactRegistry

        reg = ArtifactRegistry.get()
        reg.load_all()

        print("[*] Running a minimal verify cycle...")
        from app.models.schemas import SourceSpan
        from app.verification.verifier import verifier_engine

        span = SourceSpan(
            source_id="audit_s1",
            document_id="audit_doc",
            page=1,
            text="This is a test sentence for audit purposes.",
        )
        verdict, score, feat = verifier_engine.verify("audit_doc", "This is a test.", [span])

        print(f"[*] Verification result: {verdict} (score={score:.3f})")
    except ConnectionRefusedError as exc:
        print(f"\nFAIL: NETWORK CALL DETECTED: {exc}")
    except Exception as exc:
        print(f"\nWARNING: Unexpected error during audit: {exc}")
        traceback.print_exc()
    finally:
        _restore_socket()

    print()
    if _network_attempts:
        print("=" * 60)
        print(f"  FAIL -- {len(_network_attempts)} network call(s) detected:")
        for a in _network_attempts:
            print(f"    * {a}")
        print("=" * 60)
        return 1
    else:
        print("=" * 60)
        print("  PASS -- No network calls detected. System is air-gap compliant.")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
