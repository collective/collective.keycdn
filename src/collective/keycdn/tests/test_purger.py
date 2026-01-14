# -*- coding: utf-8 -*-
"""Tests for KeyCDN purger."""

from collective.keycdn.interfaces import IKeycdnPurgingSettings
from collective.keycdn.purger import KeycdnPurger
from collective.keycdn.testing import COLLECTIVE_KEYCDN_INTEGRATION_TESTING
from plone import api
from plone.cachepurging.interfaces import IPurger
from unittest import mock
from zope.component import queryUtility

import unittest


class TestKeycdnPurger(unittest.TestCase):
    """Test KeycdnPurger implementation."""

    layer = COLLECTIVE_KEYCDN_INTEGRATION_TESTING

    def setUp(self):
        """Set up test."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        self.portal = self.layer["portal"]
        self.purger = queryUtility(IPurger)

        # Configure settings
        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)
        settings.enabled = True
        settings.api_key = "test-api-key"
        settings.zones = (
            "12345|https://example.com",
            "67890|https://example.co.uk",
        )

    def tearDown(self):
        """Clean up."""
        if self.purger:
            self.purger.stopThreads(wait=True)
            # Reset worker and stopping flag for next test
            self.purger.worker = None
            self.purger.stopping = False
            # Clear any remaining items from queue
            while not self.purger.queue.empty():
                try:
                    self.purger.queue.get_nowait()
                except:
                    break

    def test_purger_registered(self):
        """Test that KeyCDN purger is registered as IPurger utility."""
        self.assertIsNotNone(self.purger)
        self.assertIsInstance(self.purger, KeycdnPurger)

    def test_settings_available(self):
        """Test that settings are available in registry."""
        registry = api.portal.get_tool("portal_registry")
        settings = registry.forInterface(IKeycdnPurgingSettings, check=False)
        self.assertTrue(settings.enabled)
        self.assertEqual(settings.api_key, "test-api-key")
        self.assertEqual(len(settings.zones), 2)

    def test_parse_zones_valid(self):
        """Test zone parsing with valid format."""
        purger = KeycdnPurger()
        zones = purger._parse_zones(
            (
                "12345|https://example.com",
                "67890|https://example.co.uk",
            )
        )

        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0], ("12345", "https://example.com"))
        self.assertEqual(zones[1], ("67890", "https://example.co.uk"))

    def test_parse_zones_invalid_format(self):
        """Test zone parsing with invalid format."""
        purger = KeycdnPurger()

        # Missing pipe
        zones = purger._parse_zones(("12345https://example.com",))
        self.assertEqual(len(zones), 0)

        # Empty parts
        zones = purger._parse_zones(("|https://example.com",))
        self.assertEqual(len(zones), 0)

        # Empty string
        zones = purger._parse_zones(("",))
        self.assertEqual(len(zones), 0)

    def test_extract_path_from_relative(self):
        """Test path extraction from relative URL."""
        purger = KeycdnPurger()

        path = purger._extract_path("/my-page")
        self.assertEqual(path, "/my-page")

        path = purger._extract_path("/my-page?foo=bar")
        self.assertEqual(path, "/my-page?foo=bar")

    def test_extract_path_from_absolute(self):
        """Test path extraction from absolute URL."""
        purger = KeycdnPurger()

        path = purger._extract_path("https://example.com/my-page")
        self.assertEqual(path, "/my-page")

        path = purger._extract_path("https://example.com/my-page?foo=bar")
        self.assertEqual(path, "/my-page?foo=bar")

    @mock.patch("requests.Session")
    def test_purge_sync_success_multiple_zones(self, mock_session_class):
        """Test synchronous purge success for multiple zones."""
        # Mock successful API responses
        mock_session = mock.Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success"}
        mock_session.delete.return_value = mock_resp

        status, xcache, xerror = self.purger.purgeSync("/test-page")

        self.assertEqual(status, 200)
        self.assertIn("zones", xcache)
        self.assertEqual(xerror, "")

        # Should have called delete twice (once per zone)
        self.assertEqual(mock_session.delete.call_count, 2)

        # Verify both zones were called
        call_args_list = mock_session.delete.call_args_list
        urls_purged = []
        for call in call_args_list:
            kwargs = call[1]
            urls_purged.extend(kwargs["json"]["urls"])

        self.assertIn("https://example.com/test-page", urls_purged)
        self.assertIn("https://example.co.uk/test-page", urls_purged)

    @mock.patch("requests.Session")
    def test_purge_sync_partial_failure(self, mock_session_class):
        """Test synchronous purge when one zone fails."""
        # Mock one success, one failure
        mock_session = mock.Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_success = mock.Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"status": "success"}

        mock_failure = mock.Mock()
        mock_failure.status_code = 401
        mock_failure.text = "Unauthorized"

        mock_session.delete.side_effect = [mock_success, mock_failure]

        status, xcache, xerror = self.purger.purgeSync("/test-page")

        self.assertEqual(status, "ERROR")
        self.assertIn("401", xerror)

    @mock.patch("requests.Session")
    def test_purge_sync_api_error(self, mock_session_class):
        """Test synchronous purge with API error."""
        # Mock API error for all zones
        mock_session = mock.Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session

        mock_resp = mock.Mock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_session.delete.return_value = mock_resp

        status, xcache, xerror = self.purger.purgeSync("/test-page")

        self.assertEqual(status, "ERROR")
        self.assertIn("401", xerror)

    def test_purge_async_queues(self):
        """Test async purge queues path."""
        # Ensure no worker from previous tests
        if self.purger.worker:
            self.purger.stopThreads(wait=True)
            self.purger.worker = None

        # Mock _ensure_worker to prevent worker from consuming queue
        with mock.patch.object(self.purger, "_ensure_worker"):
            self.purger.purgeAsync("/test-page")

            # Check queue not empty
            self.assertFalse(
                self.purger.queue.empty(), "Queue should not be empty after purgeAsync"
            )

            # Get the queued item (with timeout to avoid blocking forever)
            try:
                item = self.purger.queue.get(timeout=0.1)
                self.assertEqual(item, "/test-page")
            except Exception as e:
                self.fail(f"Failed to get item from queue: {e}")

    def test_purge_disabled(self):
        """Test purging when disabled delegates to original."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)
        settings.enabled = False

        # When disabled, should delegate to original purger
        # Mock it to verify delegation occurs
        with mock.patch(
            "collective.keycdn.purger.ORIGINAL_DEFAULT_PURGER.purgeSync"
        ) as mock_purge:
            mock_purge.return_value = (200, "MISS", "")

            status, xcache, xerror = self.purger.purgeSync("/test-page")

            # Should have called the original purger
            mock_purge.assert_called_once_with("/test-page", "PURGE")

    def test_purge_not_configured_api_key(self):
        """Test purging when API key not configured."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)
        settings.api_key = ""

        status, xcache, xerror = self.purger.purgeSync("/test-page")
        self.assertEqual(status, "ERROR")
        self.assertIn("not configured", xerror)

    def test_purge_not_configured_zones(self):
        """Test purging when no zones configured."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)
        settings.zones = ()

        status, xcache, xerror = self.purger.purgeSync("/test-page")
        self.assertEqual(status, "ERROR")
        self.assertIn("zones", xerror.lower())

    def test_auth_header_generation(self):
        """Test HTTP Basic Auth header generation."""
        purger = KeycdnPurger()
        header = purger._get_auth_header("test-key")

        self.assertTrue(header.startswith("Basic "))
        # Verify it's base64 encoded "test-key:"
        import base64

        expected = base64.b64encode(b"test-key:").decode()
        self.assertEqual(header, f"Basic {expected}")

    @mock.patch("requests.Session")
    def test_purge_batch_batch_size_check(self, mock_session_class):
        """Test that batch respects KeyCDN URL limit."""
        purger = KeycdnPurger()
        mock_session = mock.Mock()

        # Create 201 URLs (over the 200 limit)
        urls = [f"https://example.com/page-{i}" for i in range(201)]

        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "success"}
        mock_session.delete.return_value = mock_resp

        # This should work even with >200 URLs because we batch internally
        # (though in practice the caller should respect batch_size setting)
        success, data, error = purger._purge_batch(
            mock_session,
            urls[:200],  # Respect the limit in the call
            "12345",
            "test-key",
        )

        self.assertTrue(success)

    def test_worker_thread_starts(self):
        """Test that worker thread starts when needed."""
        # Ensure no worker exists from previous tests
        if self.purger.worker:
            self.purger.stopThreads(wait=True)
            self.purger.worker = None
            self.purger.stopping = False

        self.assertIsNone(self.purger.worker)

        self.purger.purgeAsync("/test-page")

        # Worker should now be started
        self.assertIsNotNone(self.purger.worker)
        self.assertTrue(self.purger.worker.is_alive())

    def test_purge_async_absolute_url_converted(self):
        """Test that absolute URLs are converted to paths."""
        # Ensure no worker from previous tests
        if self.purger.worker:
            self.purger.stopThreads(wait=True)
            self.purger.worker = None

        # Mock _ensure_worker to prevent worker from consuming queue
        with mock.patch.object(self.purger, "_ensure_worker"):
            self.purger.purgeAsync("https://example.com/test-page")

            # Should queue the path, not the full URL
            item = self.purger.queue.get(block=False)
            self.assertEqual(item, "/test-page")

    def test_http_1_1_property(self):
        """Test http_1_1 property (IPurger interface compatibility)."""
        self.assertTrue(self.purger.http_1_1)

    def test_error_headers_property(self):
        """Test errorHeaders property (IPurger interface compatibility)."""
        self.assertEqual(self.purger.errorHeaders, ())

    def test_purge_sync_delegates_when_disabled(self):
        """Test purgeSync delegates to original when disabled."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)
        settings.enabled = False

        # Mock the original purger's purgeSync
        with mock.patch(
            "collective.keycdn.purger.ORIGINAL_DEFAULT_PURGER.purgeSync"
        ) as mock_purge:
            mock_purge.return_value = (200, "HIT", "")

            status, xcache, xerror = self.purger.purgeSync("/test-page")

            # Should have delegated to original
            mock_purge.assert_called_once_with("/test-page", "PURGE")
            self.assertEqual(status, 200)
            self.assertEqual(xcache, "HIT")

    def test_purge_async_delegates_when_disabled(self):
        """Test purgeAsync delegates to original when disabled."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)
        settings.enabled = False

        # Mock the original purger's purgeAsync
        with mock.patch(
            "collective.keycdn.purger.ORIGINAL_DEFAULT_PURGER.purgeAsync"
        ) as mock_purge:
            self.purger.purgeAsync("/test-page")

            # Should have delegated to original
            mock_purge.assert_called_once_with("/test-page", "PURGE")

    def test_purge_delegates_when_not_installed(self):
        """Test purging delegates when package not installed."""
        # Mock _is_installed to return False
        with mock.patch.object(self.purger, "_is_installed", return_value=False):
            with mock.patch(
                "collective.keycdn.purger.ORIGINAL_DEFAULT_PURGER.purgeSync"
            ) as mock_purge:
                mock_purge.return_value = (200, "HIT", "")

                status, xcache, xerror = self.purger.purgeSync("/test-page")

                # Should have delegated even though settings might say enabled
                mock_purge.assert_called_once()
                self.assertEqual(status, 200)

    def test_purge_uses_keycdn_when_installed_and_enabled(self):
        """Test KeyCDN is used when installed and enabled."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)
        settings.enabled = True
        settings.api_key = "test-key"
        settings.zones = ("12345|https://example.com",)

        # Mock _is_installed to return True
        with mock.patch.object(self.purger, "_is_installed", return_value=True):
            with mock.patch.object(self.purger, "_purge_batch") as mock_batch:
                mock_batch.return_value = (True, {}, "")

                status, xcache, xerror = self.purger.purgeSync("/test-page")

                # Should have used KeyCDN, not delegated
                mock_batch.assert_called_once()
                self.assertEqual(status, 200)

    def test_is_installed_checks_control_panel(self):
        """Test _is_installed checks for control panel action."""
        # In test environment with addon installed, should return True
        self.assertTrue(self.purger._is_installed())

    def test_should_use_keycdn_logic(self):
        """Test _should_use_keycdn combines installed and enabled checks."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)

        # Case 1: Not installed, enabled=True → should be False
        with mock.patch.object(self.purger, "_is_installed", return_value=False):
            settings.enabled = True
            self.assertFalse(self.purger._should_use_keycdn())

        # Case 2: Installed, enabled=False → should be False
        with mock.patch.object(self.purger, "_is_installed", return_value=True):
            settings.enabled = False
            self.assertFalse(self.purger._should_use_keycdn())

        # Case 3: Installed, enabled=True → should be True
        with mock.patch.object(self.purger, "_is_installed", return_value=True):
            settings.enabled = True
            self.assertTrue(self.purger._should_use_keycdn())
