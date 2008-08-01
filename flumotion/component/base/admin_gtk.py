# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""
Base classes for component UI's using GTK+
"""

import gettext
import locale
import os

from twisted.python import util
from twisted.internet import defer

from flumotion.common import log
from flumotion.common.errors import SleepingComponentError
from flumotion.common.i18n import getLL, gettexter
from flumotion.component.base.componentnode import ComponentAdminGtkNode
from flumotion.component.base.eatersnode import EatersAdminGtkNode
from flumotion.component.base.feedersnode import FeedersAdminGtkNode
from flumotion.component.base.propertiesnode import PropertiesAdminGtkNode

_ = gettext.gettext
__version__ = "$Rev$"
T_ = gettexter()

# stupid pychecker
dir(locale)


class BaseAdminGtk(log.Loggable):
    """
    I am a base class for all GTK+-based Admin views.
    I am a view on one component's properties.

    @type nodes: L{twisted.python.util.OrderedDict}
    @ivar nodes: an ordered dict of name -> L{BaseAdminGtkNode}
    """

    logCategory = "admingtk"
    gettextDomain = None

    def __init__(self, state, admin):
        """
        @param state: state of component this is a UI for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param admin: the admin model that interfaces with the manager for us
        """
        self._debugEnabled = False
        self.state = state
        self.name = state.get('name')
        self.admin = admin
        self.debug('creating admin gtk for state %r' % state)
        self.uiState = None
        self.nodes = util.OrderedDict()

        d = admin.componentCallRemote(state, 'getUIState')
        d.addCallback(self.setUIState)
        d.addErrback(lambda failure: failure.trap(SleepingComponentError))

    def setDebugEnabled(self, enabled):
        """Set if debug should be enabled.
        Not all pages are visible unless debugging is set to true

        @param enabled: whether debug should be enabled
        @type  enabled: bool
        """
        self._debugEnabled = enabled
        for node in self.getNodes().values():
            node.setDebugEnabled(enabled)

    def cleanup(self):
        if self.uiState:
            self.uiState.removeListener(self)
            self.uiState = None
        for node in self.getNodes().values():
            node.cleanup()

    def setUIState(self, state):
        self.debug('starting listening to state %r', state)
        state.addListener(self, set_=self.stateSet, append=self.stateAppend,
                          remove=self.stateRemove)
        self.uiState = state
        for node in self.getNodes().values():
            node.gotUIState(state)
        self.uiStateChanged(state)

    def callRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state, methodName,
                                              *args, **kwargs)

    # FIXME: .setup() is subclassable, while .render() on nodes has
    # haveWidgetTree.  choose one of the two patterns in general

    def setup(self):
        """
        Set up the admin view so it can display nodes.
        """
        self.debug('BaseAdminGtk.setup()')

        def fetchTranslations():
            if not self.gettextDomain:
                return defer.succeed(None)

            def haveBundle(localedatadir):
                localeDir = os.path.join(localedatadir, 'locale')
                self.debug("Loading locales for %s from %s" % (
                    self.gettextDomain, localeDir))
                gettext.bindtextdomain(self.gettextDomain, localeDir)
                locale.bindtextdomain(self.gettextDomain, localeDir)

            lang = getLL()
            self.debug("loading bundle for %s locales" % lang)
            bundleName = '%s-locale-%s' % (self.gettextDomain, lang)
            d = self.admin.bundleLoader.getBundleByName(bundleName)
            d.addCallbacks(haveBundle, lambda _: None)
            return d

        def addPages(_):
            # FIXME: node order should be fixed somehow, so e.g. Component
            # always comes last, together with eater/feeder ?

            # add a generic component node
            self.nodes['Component'] = ComponentAdminGtkNode(self.state,
                self.admin)

            config = self.state.get('config')

            # add feeder node, if component has feeders
            if config['feed']:
                self.debug("Component has feeders, show Feeders node")
                self.nodes['Feeders'] = FeedersAdminGtkNode(
                    self.state, self.admin)

            # add eater node, if component has eaters
            if 'eater' in config and config['eater']:
                self.debug("Component has eaters, show Eaters node")
                self.nodes['Eaters'] = EatersAdminGtkNode(
                    self.state, self.admin)

            # add a properties node
            self.nodes['Properties'] = PropertiesAdminGtkNode(self.state,
                self.admin)

        d = fetchTranslations()
        d.addCallback(addPages)

        # FIXME: why are we not returning the deferred here ? If there is
        # a good reason, it should be commented here
        return

    def getNodes(self):
        """
        Return a dict of admin UI nodes.

        @rtype:   dict of str -> L{BaseAdminGtkNode}
        @returns: dict of name (untranslated) -> admin node
        """
        return self.nodes

    # FIXME: deprecated

    def render(self):
        """
        Render the GTK+ admin view for this component and return the
        main widget for embedding.
        """
        raise NotImplementedError

    def uiStateChanged(self, stateObject):
        # so, this is still here, but I'd prefer people to (1) just use
        # the nodes and not the global admin; and (2) use the state
        # listener stuff more than the chunkier 'uistatechanged'
        pass

    def stateSet(self, object, key, value):
        self.uiStateChanged(object)

    def stateAppend(self, object, key, value):
        self.uiStateChanged(object)

    def stateRemove(self, object, key, value):
        self.uiStateChanged(object)
