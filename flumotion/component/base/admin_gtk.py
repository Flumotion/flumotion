# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

import os

import gettext

import gtk
import gtk.glade

from twisted.python import util
from twisted.internet import defer

from flumotion.common import errors, log, common
from flumotion.twisted import flavors
from flumotion.twisted.defer import defer_generator_method
from flumotion.twisted.compat import implements

class BaseAdminGtk(log.Loggable):
    """
    I am a base class for all GTK+-based Admin views.
    I am a view on one component's properties.

    @type nodes: L{twisted.python.util.OrderedDict}
    @ivar nodes: an ordered dict of name -> L{BaseAdminGtkNode}
    """

    implements(flavors.IStateListener)

    logCategory = "admingtk"
    gettext_domain = 'flumotion'
    
    state = admin = nodes = 'hello pychecker'

    def __init__(self, state, admin):
        """
        @param state: state of component this is a UI for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param admin: the admin model that interfaces with the manager for us
        """
        self.state = state
        self.name = state.get('name')
        self.admin = admin
        self.debug('creating admin gtk for state %r' % state)
        self.uiState = None
        self.nodes = util.OrderedDict()

        #mid = self.status_push('Getting component information ...')
        def got_state(state):
            state.addListener(self)
            self.uiState = state
            self.uiStateChanged(state)
        d = admin.componentCallRemote(state, 'getUIState')
        d.addCallback(got_state)
        
    def propertyErrback(self, failure, window):
        failure.trap(errors.PropertyError)
        self.warning("%s." % failure.getErrorMessage())
        #window.error_dialog("%s." % failure.getErrorMessage())
        return None

    def setElementProperty(self, elementName, propertyName, value):
        """
        Set the given property on the element with the given name.
        """
        d = self.admin.setProperty(self.state, elementName, propertyName, value)
        d.addErrback(self.propertyErrback, self)
        return d
    
    def getElementProperty(self, elementName, propertyName):
        """
        Get the value of the given property of the element with the given name.
        
        Returns: L{twisted.internet.defer.Deferred} returning the value.
        """
        d = self.admin.getProperty(self.state, elementName, propertyName)
        d.addErrback(self.propertyErrback, self)
        return d

    def callRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state, methodName,
                                              *args, **kwargs)
        
    ### child class methods to be overridden
    def setUIState(self, state):
        # FIXME: what is this? who implements this?
        raise NotImplementedError

    def propertyChanged(self, name, value):
        """
        Override this method to be notified of component's properties that
        have changed.

        I am meant to be overridden.
        """
        self.debug("property %s changed to %r" % (name, value))

    # FIXME: .setup() is subclassable, while .render() on nodes has
    # haveWidgetTree.  choose one of the two patterns in general
    def setup(self):
        """
        Set up the admin view so it can display nodes.
        """
        self.debug('BaseAdminGtk.setup()')
        # set up translations
        if not hasattr(self, 'gettext_domain'):
            yield None

        lang = common.getLL()
        self.debug("loading bundle for %s locales" % lang)
        bundleName = '%s-locale-%s' % (self.gettext_domain, lang)
        d = self.admin.bundleLoader.getBundleByName(bundleName)
        yield d

        try:
            localedatadir = d.value()
        except errors.NoBundleError:
            self.debug("Failed to find locale bundle %s" % bundleName)
            yield None

        localeDir = os.path.join(localedatadir, 'locale')
        self.debug("Loading locales for %s from %s" % (
            self.gettext_domain, localeDir))
        gettext.bindtextdomain(self.gettext_domain, localeDir)
        gtk.glade.bindtextdomain(self.gettext_domain, localeDir)
        yield None
    setup = defer_generator_method(setup)

    def getNodes(self):
        """
        Return a dict of admin UI nodes.
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
        # default implementation
        pass

    def stateSet(self, object, key, value):
        self.uiStateChanged(object)

    def stateAppend(self, object, key, value):
        self.uiStateChanged(object)

    def stateRemove(self, object, key, value):
        self.uiStateChanged(object)

class BaseAdminGtkNode(log.Loggable):
    """
    I am a base class for all GTK+-based Admin UI nodes.
    I am a view on a set of properties for a component.

    @ivar widget: the main widget representing this node
    @type widget: L{gtk.Widget}
    @ivar wtree:  the widget tree representation for this node
    """
    logCategory = "admingtk"
    glade_file = None
    gettext_domain = 'flumotion'

    def __init__(self, state, admin, title=None):
        """
        @param state: state of component this is a UI node for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @param admin: the admin model that interfaces with the manager for us
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param title: the (translated) title to show this node with
        @type  title: str
        """
        self.state = state
        self.admin = admin
        self.statusbar = None
        self.title = title
        self.nodes = util.OrderedDict()
        self.wtree = None
        self.widget = None
        
    def status_push(self, str):
        if self.statusbar:
            return self.statusbar.push('notebook', str)

    def status_pop(self, mid):
        if self.statusbar:
            return self.statusbar.remove('notebook', mid)

    def propertyErrback(self, failure, window):
        failure.trap(errors.PropertyError)
        self.warning("%s." % failure.getErrorMessage())
        #window.error_dialog("%s." % failure.getErrorMessage())
        return None

    def setElementProperty(self, elementName, propertyName, value):
        """
        Set the given property on the element with the given name.
        """
        d = self.admin.setProperty(self.state, elementName, propertyName, value)
        d.addErrback(self.propertyErrback, self)
        return d
    
    def getElementProperty(self, elementName, propertyName):
        """
        Get the value of the given property of the element with the given name.
        
        Returns: L{twisted.internet.defer.Deferred} returning the value.
        """
        d = self.admin.getProperty(self.state, elementName, propertyName)
        d.addErrback(self.propertyErrback, self)
        return d

    def callRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state, methodName,
                                              *args, **kwargs)
       
    # FIXME: do this automatically if there is a gladeFile class attr set
    def loadGladeFile(self, gladeFile, domain='flumotion'):
        """
        Returns: a deferred returning the widget tree from the glade file.
        """
        def _getBundledFileCallback(result, gladeFile):
            path = result
            if not os.path.exists(path):
                self.warning("Glade file %s not found in path %s" % (
                    gladeFile, path))
            self.debug("Switching glade text domain to %s" % domain)
            self.debug("loading widget tree from %s" % path)
            old = gtk.glade.textdomain()
            gtk.glade.textdomain(domain)
            self.wtree = gtk.glade.XML(path)
            self.debug("Switching glade text domain back to %s" % old)
            gtk.glade.textdomain(old)
            return self.wtree

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

    def haveWidgetTree(self):
        """
        I am called when the widget tree has been gotten from the glade file.

        Override me to act on it.

        Returns: L{twisted.internet.defer.Deferred}
        """
        return defer.succeed(None)

    def propertyChanged(self, name, value):
        """
        I am meant to be overridden.
        """
        self.debug("property %s changed to %r" % (name, value))

    def render(self):
        """
        Render the GTK+ admin view for this component.
        
        Returns: a deferred returning the main widget for embedding
        """
        if hasattr(self, 'glade_file'):
            self.debug('render: loading glade file %s in text domain %s' % (
                self.glade_file, self.gettext_domain))
            dl = self.loadGladeFile(self.glade_file, self.gettext_domain)
            yield dl

            try:
                self.wtree = dl.value()
            except RuntimeError:
                msg = 'Could not load glade file %s' % self.glade_file
                self.warning(msg)
                yield gtk.Label("%s.  Kill the programmer." % msg)

            self.debug('render: calling haveWidgetTree')
            dh = self.haveWidgetTree()
            yield dh
            
        if not self.widget:
            self.debug('render: no self.widget, failing')
            yield defer.fail(IndexError)
            
        self.debug('render: yielding widget %s' % self.widget)
        yield self.widget
    render = defer_generator_method(render)

class EffectAdminGtkNode(BaseAdminGtkNode):
    """
    I am a base class for all GTK+-based component effect Admin UI nodes.
    I am a view on a set of properties for an effect on a component.

    """
    def __init__(self, state, admin, effectName, title=None):
        """
        @param state: state of component this is a UI for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @param admin: the admin model that interfaces with the manager for us
        @type  admin: L{flumotion.admin.admin.AdminModel}
        """
        BaseAdminGtkNode.__init__(self, state, admin, title)
        self.effectName = effectName

    def effectCallRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state,
            "effect", self.effectName, methodName, *args, **kwargs)
