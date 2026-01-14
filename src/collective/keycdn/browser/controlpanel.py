# -*- coding: utf-8 -*-
"""KeyCDN control panel."""

from collective.keycdn import _
from collective.keycdn.interfaces import IKeycdnPurgingSettings
from plone.app.registry.browser import controlpanel


class KeycdnSettingsEditForm(controlpanel.RegistryEditForm):
    """KeyCDN settings form."""

    schema = IKeycdnPurgingSettings
    label = _("KeyCDN Settings")
    description = _(
        "Configure KeyCDN cache purging for your Plone site. "
        "You need a KeyCDN account and API key to use this functionality. "
        "For multi-domain sites using Virtual Host Monster, configure multiple zones "
        "in the format 'zone_id|https://domain.com'."
    )

    def updateFields(self):
        """Customize fields if needed."""
        super().updateFields()
        # Can customize field order or properties here if needed

    def updateWidgets(self):
        """Customize widgets if needed."""
        super().updateWidgets()
        # Can add custom widget hints or descriptions here


class KeycdnSettingsControlPanel(controlpanel.ControlPanelFormWrapper):
    """KeyCDN settings control panel wrapper."""

    form = KeycdnSettingsEditForm
