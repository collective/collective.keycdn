# -*- coding: utf-8 -*-
"""Control panel tests."""

from collective.keycdn.testing import COLLECTIVE_KEYCDN_INTEGRATION_TESTING
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import unittest


class TestControlPanel(unittest.TestCase):
    """Test that collective.keycdn control panel is properly configured."""

    layer = COLLECTIVE_KEYCDN_INTEGRATION_TESTING

    def setUp(self):
        """Setup test."""
        self.portal = self.layer["portal"]
        self.request = self.layer["request"]
        setRoles(self.portal, TEST_USER_ID, ["Manager"])

    def test_controlpanel_installed(self):
        """Test that control panel is registered."""
        controlpanel = api.portal.get_tool("portal_controlpanel")
        actions = [a.getId() for a in controlpanel.listActions()]
        self.assertIn("keycdn", actions)

    def test_controlpanel_view_protected(self):
        """Test that control panel view requires permission."""
        from AccessControl import Unauthorized

        # Anonymous should not be able to access
        setRoles(self.portal, TEST_USER_ID, [])
        with self.assertRaises(Unauthorized):
            self.portal.restrictedTraverse("@@keycdn-settings")

    def test_controlpanel_view_accessible_by_manager(self):
        """Test that managers can access control panel."""
        setRoles(self.portal, TEST_USER_ID, ["Manager"])
        view = self.portal.restrictedTraverse("@@keycdn-settings")
        self.assertIsNotNone(view)

    def test_controlpanel_has_correct_title(self):
        """Test that control panel has correct title."""
        controlpanel = api.portal.get_tool("portal_controlpanel")
        actions = [a for a in controlpanel.listActions() if a.getId() == "keycdn"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].Title(), "KeyCDN Settings")

    def test_settings_editable(self):
        """Test that settings can be changed via API."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)

        settings.api_key = "test-key"
        self.assertEqual(settings.api_key, "test-key")

    def test_zones_editable(self):
        """Test that zones can be configured."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)

        settings.zones = ("12345|https://example.com", "67890|https://example.co.uk")
        self.assertEqual(len(settings.zones), 2)
        self.assertEqual(settings.zones[0], "12345|https://example.com")
        self.assertEqual(settings.zones[1], "67890|https://example.co.uk")

    def test_batch_size_validation(self):
        """Test that batch_size has proper constraints."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)

        # Valid value
        settings.batch_size = 50
        self.assertEqual(settings.batch_size, 50)

        # Test boundary values
        settings.batch_size = 1
        self.assertEqual(settings.batch_size, 1)

        settings.batch_size = 200
        self.assertEqual(settings.batch_size, 200)

    def test_enabled_setting(self):
        """Test that purging can be enabled/disabled."""
        from collective.keycdn.interfaces import IKeycdnPurgingSettings
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IKeycdnPurgingSettings)

        settings.enabled = False
        self.assertFalse(settings.enabled)

        settings.enabled = True
        self.assertTrue(settings.enabled)
