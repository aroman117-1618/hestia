"""Tests for SentinelConfig — written first (TDD)."""
import json
import os
import tempfile
import unittest


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


MASTER_CONFIG = {
    "containment_enabled": False,
    "learning_mode": True,
    "file_integrity_interval_seconds": 300,
    "credential_watch_interval_seconds": 30,
    "dns_monitor_enabled": True,
    "heartbeat_url": "",
    "heartbeat_interval_seconds": 300,
    "daily_digest_hour": 8,
    "max_crashes_before_shutdown": 3,
    "crash_window_seconds": 300,
}

DNS_ALLOWLIST = {
    "domains": [
        "api.coinbase.com",
        "api.alpaca.markets",
        "*.tailscale.com",
        "api.anthropic.com",
        "api.openai.com",
        "generativelanguage.googleapis.com",
        "github.com",
        "*.githubusercontent.com",
        "pypi.org",
        "files.pythonhosted.org",
        "localhost",
        "*.apple.com",
        "*.icloud.com",
        "ntfy.sh",
        "hc-ping.com",
    ]
}

PROCESS_ALLOWLIST = {
    "credential_access": {
        "coinbase-credentials": ["bot_service", "python3"],
        "cloud_api_key": ["hestia.api.server", "python3"],
    }
}


class TestSentinelConfigBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _write_json(os.path.join(self.tmpdir, "sentinel.json"), MASTER_CONFIG)
        _write_json(os.path.join(self.tmpdir, "sentinel-dns-allowlist.json"), DNS_ALLOWLIST)
        _write_json(os.path.join(self.tmpdir, "sentinel-process-allowlist.json"), PROCESS_ALLOWLIST)

        from hestia.sentinel.config import SentinelConfig
        self.cfg = SentinelConfig(self.tmpdir)


class TestConfigLoadsMasterConfig(TestSentinelConfigBase):
    def test_containment_enabled(self):
        self.assertFalse(self.cfg.containment_enabled)

    def test_learning_mode(self):
        self.assertTrue(self.cfg.learning_mode)

    def test_file_integrity_interval(self):
        self.assertEqual(self.cfg.file_integrity_interval, 300)

    def test_credential_watch_interval(self):
        self.assertEqual(self.cfg.credential_watch_interval, 30)

    def test_dns_monitor_enabled(self):
        self.assertTrue(self.cfg.dns_monitor_enabled)

    def test_heartbeat_url(self):
        self.assertEqual(self.cfg.heartbeat_url, "")

    def test_heartbeat_interval(self):
        self.assertEqual(self.cfg.heartbeat_interval, 300)

    def test_daily_digest_hour(self):
        self.assertEqual(self.cfg.daily_digest_hour, 8)

    def test_max_crashes(self):
        self.assertEqual(self.cfg.max_crashes, 3)

    def test_crash_window(self):
        self.assertEqual(self.cfg.crash_window, 300)


class TestConfigLoadsDnsAllowlist(TestSentinelConfigBase):
    def test_exact_domain_allowed(self):
        self.assertTrue(self.cfg.is_domain_allowed("api.coinbase.com"))

    def test_another_exact_domain_allowed(self):
        self.assertTrue(self.cfg.is_domain_allowed("pypi.org"))

    def test_unlisted_domain_blocked(self):
        self.assertFalse(self.cfg.is_domain_allowed("evil.com"))

    def test_subdomain_of_exact_domain_blocked(self):
        # pypi.org is listed exactly; sub.pypi.org is not allowed
        self.assertFalse(self.cfg.is_domain_allowed("sub.pypi.org"))

    def test_localhost_allowed(self):
        self.assertTrue(self.cfg.is_domain_allowed("localhost"))


class TestConfigWildcardMatching(TestSentinelConfigBase):
    def test_wildcard_subdomain_allowed(self):
        # *.tailscale.com should match derp.tailscale.com
        self.assertTrue(self.cfg.is_domain_allowed("derp.tailscale.com"))

    def test_wildcard_apex_allowed(self):
        # *.tailscale.com should also match tailscale.com itself
        self.assertTrue(self.cfg.is_domain_allowed("tailscale.com"))

    def test_wildcard_does_not_match_attacker_suffix(self):
        # evil.tailscale.com.attacker.net must NOT match *.tailscale.com
        self.assertFalse(self.cfg.is_domain_allowed("evil.tailscale.com.attacker.net"))

    def test_wildcard_apple_subdomain(self):
        self.assertTrue(self.cfg.is_domain_allowed("www.apple.com"))

    def test_wildcard_apple_apex(self):
        self.assertTrue(self.cfg.is_domain_allowed("apple.com"))

    def test_wildcard_does_not_match_partial_suffix(self):
        # notapple.com should NOT match *.apple.com
        self.assertFalse(self.cfg.is_domain_allowed("notapple.com"))

    def test_wildcard_githubusercontent_subdomain(self):
        self.assertTrue(self.cfg.is_domain_allowed("raw.githubusercontent.com"))


class TestConfigLoadsProcessAllowlist(TestSentinelConfigBase):
    def test_allowed_process_for_credential(self):
        self.assertTrue(self.cfg.is_process_allowed("coinbase-credentials", "bot_service"))

    def test_another_allowed_process(self):
        self.assertTrue(self.cfg.is_process_allowed("coinbase-credentials", "python3"))

    def test_blocked_process_for_credential(self):
        self.assertFalse(self.cfg.is_process_allowed("coinbase-credentials", "curl"))

    def test_allowed_process_cloud_api_key(self):
        self.assertTrue(self.cfg.is_process_allowed("cloud_api_key", "hestia.api.server"))

    def test_unknown_credential_blocks_all(self):
        self.assertFalse(self.cfg.is_process_allowed("unknown-cred", "python3"))


class TestConfigReload(TestSentinelConfigBase):
    def test_reload_picks_up_changes(self):
        # Change containment_enabled to True on disk, then reload
        updated = dict(MASTER_CONFIG, containment_enabled=True)
        _write_json(os.path.join(self.tmpdir, "sentinel.json"), updated)
        self.cfg.reload()
        self.assertTrue(self.cfg.containment_enabled)


if __name__ == "__main__":
    unittest.main()
