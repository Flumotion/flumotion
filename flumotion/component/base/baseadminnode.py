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

import gettext
import os

import gtk
import gtk.glade
from twisted.python import util
from twisted.internet import defer
from zope.interface import implements

from flumotion.common import errors, log, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.configure import configure
from flumotion.twisted import flavors
from flumotion.ui.fgtk import ProxyWidgetMapping

_ = gettext.gettext
__version__ = "$Rev$"
T_ = gettexter()


class BaseAdminGtkNode(log.Loggable):
    """
    I am a base class for all GTK+-based Admin UI nodes.
    I am a view on a set of properties for a component.

    @ivar widget: the main widget representing this node
    @type widget: L{gtk.Widget}
    @ivar wtree:  the widget tree representation for this node
    """

    implements(flavors.IStateListener)

    logCategory = "admingtk"
    gladeFile = None ## Relative path of the glade file.
                      ##   e.g. "flumotion/ui.glade"
    gettextDomain = configure.PACKAGE

    def __init__(self, state, admin, title=None):
        """
        @param state: state of component this is a UI node for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @param admin: the admin model that interfaces with the manager for us
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param title: the (translated) title to show this node with
        @type  title: str
        """
        self._debugEnabled = False
        self.state = state
        self.admin = admin
        self.statusbar = None
        self.title = title
        self.nodes = util.OrderedDict()
        self.wtree = None # glade.XML instance (optionally set)
        self.widget = None # the top level widget that will be visible
        self.uiState = None # set if we are listening
        self._pendingUIState = None # set if we are waiting for the ui
                                    # to load
        ## Absolute path to the glade file.
        ##   e.g. "/home/flu/.flumotion/cache/test/80...df7/flumotion/ui.glade
        self._gladefilepath = None

    def setDebugEnabled(self, enabled):
        """Set if debug should be enabled.
        Not all pages are visible unless debugging is set to true

        @param enabled: whether debug should be enabled
        @type  enabled: bool
        """
        self._debugEnabled = enabled

    def cleanup(self):
        if self.uiState:
            self.uiState.removeListener(self)

    def status_push(self, str):
        if self.statusbar:
            return self.statusbar.push('notebook', str)

    def status_pop(self, mid):
        if self.statusbar:
            return self.statusbar.remove('notebook', mid)

    def callRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state, methodName,
                                              *args, **kwargs)

    # FIXME: do this automatically if there is a gladeFile class attr set

    def loadGladeFile(self, gladeFile, domain=configure.PACKAGE):
        """
        Returns: a deferred returning the widget tree from the glade file.
        """

        def _getBundledFileCallback(result, gladeFile):
            path = result
            if not os.path.exists(path):
                self.warning("Glade file %s not found in path %s" % (
                    gladeFile, path))
            self.debug("loading widget tree from %s" % path)

            old = gtk.glade.textdomain()
            self.debug("Switching glade text domain from %s to %s" % (
                old, domain))
            self._gladefilepath = path
            gtk.glade.textdomain(domain)

            self.wtree = gtk.glade.XML(path,
                                       typedict=ProxyWidgetMapping())

            self.debug("Switching glade text domain back from %s to %s" % (
                domain, old))
            gtk.glade.textdomain(old)
            return self.wtree

        # The manager is always using / as a path separator, to avoid
        # confusion, convert os.path.sep -> / here.
        gladeFile = gladeFile.replace(os.path.sep, '/')
        # FIXME: this does needless roundtrips; should instead be
        # loading from the already-downloaded paths
        self.debug("requesting bundle for glade file %s" % gladeFile)
        d = self.admin.bundleLoader.getFile(gladeFile)
        d.addCallback(_getBundledFileCallback, gladeFile)
        return d

    def getWidget(self, name):
        if not self.wtree:
            raise IndexError
        widget = self.wtree.get_widget(name)
        if not widget:
            self.warning('Could not get widget %s' % name)

        return widget

    def createWidget(self, name):
        """
        Create a new widget instance from the glade file.
        Can be used to make multiple instances of the same widget.
        """
        if not self._gladefilepath:
            raise IndexError
        wtree = gtk.glade.XML(self._gladefilepath, name,
                              typedict=ProxyWidgetMapping())
        widget = wtree.get_widget(name)
        if not widget:
            self.warning('Could not create widget %s' % name)

        return widget

    def haveWidgetTree(self):
        """
        I am called when the widget tree has been gotten from the glade
        file. Responsible for setting self.widget.

        Override me to act on it.
        """
        pass

    def gotUIState(self, state):
        if self.widget:
            self.setUIState(state)
        else:
            self._pendingUIState = state

    def setUIState(self, state):
        """
        Called by the BaseAdminGtk when it gets the UI state and the GUI
        is ready. Chain up if you provide your own implementation.
        """
        self.uiState = state
        state.addListener(self, set_=self.stateSet, append=self.stateAppend,
                          remove=self.stateRemove, setitem=self.stateSetitem,
                          delitem=self.stateDelitem)

    def stateSet(self, state, key, value):
        "Override me"
        pass

    def stateAppend(self, state, key, value):
        "Override me"
        pass

    def stateRemove(self, state, key, value):
        "Override me"
        pass

    def stateSetitem(self, state, key, subkey, value):
        "Override me"
        pass

    def stateDelitem(self, state, key, subkey, value):
        "Override me"
        pass

    def render(self):
        """
        Render the GTK+ admin view for this component.

        Returns: a deferred returning the main widget for embedding
        """
        self.debug('BaseAdminGtkNode.render() for %s' % self.title)

        # clear up previous error messages
        allmessages = self.state.get('messages', [])
        for message in allmessages:
            # since we can have multiple nodes, only remove the one from
            # ours; this assumes each node's title is unique for a component
            if message.id == 'render-%s' % self.title:
                self.debug('Removing previous messages %r' % message)
                self.state.observe_remove('messages', message)

        def error(debug):
            # add an error message to the component and return
            # an error label, given a debug string
            self.warning("error rendering component UI; debug %s", debug)
            m = messages.Error(T_(N_(
                "Internal error in component UI's '%s' tab.  "
                "Please file a bug against the component."), self.title),
                debug=debug, mid="render-%s" % self.title)
            self.addMessage(m)

            label = gtk.Label(_("Internal error.\nSee component error "
                    "message\nfor more details."))

            # if we don't set this error as our label, we will raise
            # a TypeError below and obscure this more meaningful error
            self.widget = label

            return label

        def loadGladeFile():
            # F0.8
            if hasattr(self, 'glade_file'):
                self.gladeFile = self.glade_file
                debug = "class %r should have glade_file " \
                    "changed to gladeFile" % self.__class__
                import warnings
                warnings.warn(debug, DeprecationWarning)
                m = messages.Warning(T_(N_(
                    "Internal error in component UI's '%s' tab.  "
                    "Please file a bug against the component."), self.title),
                    debug=debug, mid="render-%s" % self.title)
                self.addMessage(m)

            if not self.gladeFile:
                return defer.succeed(None)

            def haveWtree(wtree):
                self.wtree = wtree
                self.debug('render: calling haveWidgetTree')
                try:
                    self.haveWidgetTree()
                except Exception, e:
                    return error(log.getExceptionMessage(e))

            self.debug('render: loading glade file %s in text domain %s',
                       self.gladeFile, self.gettextDomain)

            d = self.loadGladeFile(self.gladeFile, self.gettextDomain)
            d.addCallback(haveWtree)
            return d

        def loadGladeFileErrback(failure):
            if failure.check(RuntimeError):
                return error(
                    'Could not load glade file %s.' % self.gladeFile)
            if failure.check(errors.NoBundleError):
                return error(
                    'No bundle found containing %s.' % self.gladeFile)

            return failure

        def renderFinishedCallback(_):
            if not self.widget:
                self.debug('render: no self.widget, failing')
                raise TypeError(
                    '%r.haveWidgetTree should have set self.widget' %
                        self.__class__)

            if self._pendingUIState:
                self.debug('render: calling setUIState on the node')
                self.setUIState(self._pendingUIState)

            self.debug('renderFinished: returning widget %s', self.widget)
            return self.widget

        def renderFinishedErrback(failure):
            return error(log.getFailureMessage(failure))

        d = loadGladeFile()
        d.addErrback(loadGladeFileErrback)
        d.addCallback(renderFinishedCallback)
        d.addErrback(renderFinishedErrback)
        return d

    def addMessage(self, message):
        """
        Add a message to the component.
        Since this is called in a component view and only relevant to the
        component view, the message only exists in the view, and is not
        replicated to the manager state.

        The message will be displayed in the usual message view.

        @type  message: L{flumotion.common.messages.Message}
        """
        self.state.observe_append('messages', message)
