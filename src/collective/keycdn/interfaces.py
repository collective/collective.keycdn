# -*- coding: utf-8 -*-
"""Module where all interfaces, events and exceptions live."""

from zope import schema
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class ICollectiveKeycdnLayer(IDefaultBrowserLayer):
    """Marker interface that defines a browser layer."""


class IKeycdnPurgingSettings(Interface):
    """Settings for KeyCDN cache purging."""

    enabled = schema.Bool(
        title=u"Enable KeyCDN purging",
        description=u"If disabled, no purging will occur via KeyCDN",
        default=False
    )

    api_key = schema.TextLine(
        title=u"KeyCDN API Key",
        description=u"Your KeyCDN API key for authentication. "
                    u"This key is shared across all zones.",
        required=False,
        default=u"",
    )

    zones = schema.Tuple(
        title=u"KeyCDN Zones",
        description=u"List of zone_id|base_domain pairs for virtual hosting support. "
                    u"Format: 'zone_id|https://example.com'. "
                    u"Example: ('12345|https://example.com', '67890|https://example.co.uk')",
        value_type=schema.TextLine(),
        required=False,
        default=(),
    )

    batch_size = schema.Int(
        title=u"Batch Size",
        description=u"Maximum number of URLs to purge in a single API call per zone. "
                    u"KeyCDN allows up to 200 URLs per request.",
        default=50,
        required=True,
        min=1,
        max=200,
    )

    timeout = schema.Int(
        title=u"API Timeout",
        description=u"Timeout in seconds for KeyCDN API requests",
        default=30,
        required=True,
        min=1,
    )
