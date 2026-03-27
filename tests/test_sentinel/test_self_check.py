"""
Tests for SelfCheck — self-integrity verification via SHA-256 manifests.
Written BEFORE implementation (TDD).
"""

import json
import os
import tempfile

import pytest

from hestia.sentinel.self_check import SelfCheck


class TestGenerateManifest:
    def test_generate_manifest_correct_entries_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_a = os.path.join(tmpdir, "a.py")
            file_b = os.path.join(tmpdir, "b.py")
            with open(file_a, "w") as f:
                f.write("print('hello')")
            with open(file_b, "w") as f:
                f.write("print('world')")

            manifest = SelfCheck.generate_manifest([file_a, file_b])

            assert len(manifest) == 2
            assert file_a in manifest
            assert file_b in manifest
            for path, digest in manifest.items():
                assert len(digest) == 64
                assert all(c in "0123456789abcdef" for c in digest)


class TestVerifyPassesWhenClean:
    def test_verify_returns_true_for_unmodified_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_a = os.path.join(tmpdir, "module.py")
            with open(file_a, "w") as f:
                f.write("x = 1")

            manifest = SelfCheck.generate_manifest([file_a])
            assert SelfCheck.verify(manifest) is True


class TestVerifyFailsWhenTampered:
    def test_verify_returns_false_after_file_modification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_a = os.path.join(tmpdir, "target.py")
            with open(file_a, "w") as f:
                f.write("original content")

            manifest = SelfCheck.generate_manifest([file_a])

            # Tamper with the file
            with open(file_a, "w") as f:
                f.write("tampered content")

            assert SelfCheck.verify(manifest) is False


class TestVerifyFailsWhenFileMissing:
    def test_verify_returns_false_for_nonexistent_path(self):
        manifest = {"/nonexistent/path/does_not_exist.py": "a" * 64}
        assert SelfCheck.verify(manifest) is False


class TestSaveAndLoadManifest:
    def test_round_trip_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_a = os.path.join(tmpdir, "code.py")
            manifest_path = os.path.join(tmpdir, "manifest.json")

            with open(file_a, "w") as f:
                f.write("def foo(): pass")

            manifest = SelfCheck.generate_manifest([file_a])
            SelfCheck.save_manifest(manifest, manifest_path)

            loaded = SelfCheck.load_manifest(manifest_path)

            assert loaded == manifest
            assert isinstance(loaded, dict)
            # Confirm it's valid JSON on disk
            with open(manifest_path) as f:
                raw = json.load(f)
            assert raw == manifest
