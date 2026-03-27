"""Tests for FileIntegrityAdapter — TDD, stdlib only."""
import os
import tempfile

import pytest

from hestia.sentinel.baseline import BaselineManager
from hestia.sentinel.adapters.file_integrity import FileIntegrityAdapter


class TestFileIntegrityAdapterDetectsNewPth:
    def test_file_integrity_adapter_detects_new_pth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            site_packages = os.path.join(tmpdir, "site-packages")
            os.makedirs(site_packages)

            existing = os.path.join(site_packages, "existing.pth")
            with open(existing, "w") as f:
                f.write("/some/path\n")

            baseline_path = os.path.join(tmpdir, "baseline.json")
            mgr = BaselineManager(baseline_path)
            mgr.create_baseline(site_packages)

            # Add malicious .pth after baseline
            malicious = os.path.join(site_packages, "malicious.pth")
            with open(malicious, "w") as f:
                f.write("/evil/inject\n")

            adapter = FileIntegrityAdapter(site_packages, mgr)
            events = adapter.poll()

            assert len(events) == 1
            event = events[0]
            assert event["severity"] == "CRITICAL"
            assert "malicious.pth" in event["summary"]
            assert event["event_id"] is not None
            assert len(event["event_id"]) == 32  # uuid4 hex


class TestFileIntegrityAdapterClean:
    def test_file_integrity_adapter_clean(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            site_packages = os.path.join(tmpdir, "site-packages")
            os.makedirs(site_packages)

            good = os.path.join(site_packages, "good.pth")
            with open(good, "w") as f:
                f.write("/legit/path\n")

            baseline_path = os.path.join(tmpdir, "baseline.json")
            mgr = BaselineManager(baseline_path)
            mgr.create_baseline(site_packages)

            adapter = FileIntegrityAdapter(site_packages, mgr)
            events = adapter.poll()

            assert events == []
