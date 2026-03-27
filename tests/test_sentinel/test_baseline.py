"""Tests for BaselineManager — TDD, stdlib only."""
import json
import os
import tempfile

import pytest

from hestia.sentinel.baseline import BaselineManager


class TestCreateBaseline:
    def test_create_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            site_packages = os.path.join(tmpdir, "site-packages")
            os.makedirs(site_packages)

            # Create some .pth files
            pth1 = os.path.join(site_packages, "foo.pth")
            pth2 = os.path.join(site_packages, "bar.pth")
            with open(pth1, "w") as f:
                f.write("/some/path\n")
            with open(pth2, "w") as f:
                f.write("/another/path\n")

            baseline_path = os.path.join(tmpdir, "baseline.json")
            mgr = BaselineManager(baseline_path)
            mgr.create_baseline(site_packages)

            assert os.path.exists(baseline_path)
            with open(baseline_path) as f:
                data = json.load(f)

            assert "foo.pth" in data
            assert "bar.pth" in data
            # Each entry should have a sha256 hash (64 hex chars)
            assert len(data["foo.pth"]) == 64
            assert len(data["bar.pth"]) == 64


class TestDiffDetectsNewPth:
    def test_diff_detects_new_pth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            site_packages = os.path.join(tmpdir, "site-packages")
            os.makedirs(site_packages)

            pth1 = os.path.join(site_packages, "existing.pth")
            with open(pth1, "w") as f:
                f.write("/some/path\n")

            baseline_path = os.path.join(tmpdir, "baseline.json")
            mgr = BaselineManager(baseline_path)
            mgr.create_baseline(site_packages)

            # Add a new .pth after baseline was taken
            pth2 = os.path.join(site_packages, "malicious.pth")
            with open(pth2, "w") as f:
                f.write("/evil/path\n")

            changes = mgr.diff(site_packages)

            assert len(changes) == 1
            change = changes[0]
            assert change["type"] == "new_pth"
            assert "malicious.pth" in change["path"]
            assert "hash" in change


class TestDiffCleanWhenUnchanged:
    def test_diff_clean_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            site_packages = os.path.join(tmpdir, "site-packages")
            os.makedirs(site_packages)

            pth1 = os.path.join(site_packages, "good.pth")
            with open(pth1, "w") as f:
                f.write("/some/path\n")

            baseline_path = os.path.join(tmpdir, "baseline.json")
            mgr = BaselineManager(baseline_path)
            mgr.create_baseline(site_packages)

            changes = mgr.diff(site_packages)

            assert changes == []
