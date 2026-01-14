# -*- coding: utf-8 -*-
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer

import collective.keycdn


class CollectiveKeycdnLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load any other ZCML that is required for your tests.
        # The z3c.autoinclude feature is disabled in the Plone fixture base
        # layer.
        import plone.app.dexterity

        self.loadZCML(package=plone.app.dexterity)
        import plone.restapi

        self.loadZCML(package=plone.restapi)

        # Load plone.cachepurging before collective.keycdn
        # so our purger overrides the default
        import plone.cachepurging

        self.loadZCML(package=plone.cachepurging)
        self.loadZCML(package=collective.keycdn)

    def setUpPloneSite(self, portal):
        applyProfile(portal, "collective.keycdn:default")


COLLECTIVE_KEYCDN_FIXTURE = CollectiveKeycdnLayer()


COLLECTIVE_KEYCDN_INTEGRATION_TESTING = IntegrationTesting(
    bases=(COLLECTIVE_KEYCDN_FIXTURE,),
    name="CollectiveKeycdnLayer:IntegrationTesting",
)


COLLECTIVE_KEYCDN_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(COLLECTIVE_KEYCDN_FIXTURE,),
    name="CollectiveKeycdnLayer:FunctionalTesting",
)
