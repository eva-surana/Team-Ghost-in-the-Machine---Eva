"""
connectivity.py — Fast online/offline reachability check.

Called ONLY when ENABLE_ONLINE_RECOMMENDATIONS=true.
Uses a short timeout (2–3 s) against a single known-reliable host.
Never imported by the core pipeline.
"""
from __future__ import annotations

import logging
import socket

logger = logging.getLogger(__name__)

_CHECK_HOST = "api.semanticscholar.org"
_CHECK_PORT = 443
_TIMEOUT_S = 3.0


def is_online() -> bool:
    """
    Return True if the Semantic Scholar API host is reachable within timeout.
    Swallows all exceptions — a connectivity failure is never a fatal error.
    """
    try:
        socket.setdefaulttimeout(_TIMEOUT_S)
        with socket.create_connection((_CHECK_HOST, _CHECK_PORT), timeout=_TIMEOUT_S):
            return True
    except OSError:
        return False
    finally:
        socket.setdefaulttimeout(None)
