"""
Pytest configuration and shared fixtures.

Key behavior: force-kills ChromaDB background threads after test session
completes to prevent the well-known process hang (chromadb's WAL flushing
and compaction threads are non-daemon and block interpreter exit).
"""

import os
import threading


def pytest_sessionfinish(session, exitstatus):
    """Force-terminate lingering ChromaDB threads after all tests complete.

    ChromaDB's PersistentClient spawns non-daemon background threads for
    write-ahead log flushing and compaction. These threads run infinite
    loops and prevent the Python process from exiting, causing pytest to
    hang indefinitely after all tests pass.

    This hook identifies those threads and calls os._exit() to force a
    clean shutdown, preserving the original pytest exit code.
    """
    # Check for non-daemon threads that would block exit
    alive_threads = [
        t for t in threading.enumerate()
        if t.is_alive() and not t.daemon and t is not threading.main_thread()
    ]

    if alive_threads:
        # Force exit with the pytest exit code — this kills all threads
        os._exit(exitstatus)
