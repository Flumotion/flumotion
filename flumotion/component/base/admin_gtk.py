# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import os

import gtk
import gtk.glade

from flumotion.common import errors, log

class BaseAdminGtk(log.Loggable):
    """
    I am a base class for all GTK+-based Admin views.
    I am a view on one component's properties.
    """

    logCategory = "admingtk"
    
    def __init__(self, state, admin, view):
        """
        @param state: state of component this is a UI for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param admin: the admin model that interfaces with the manager for us
        @type  view:   
        @param view:  the toolkit view we are embedded in
        """
        self.state = state
        self.name = state.get('name')
        self.admin = admin
        self.view = view
        self.debug('creating admin gtk for state %r' % state)
        
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
        
    # FIXME: deprecated, moved to node
    # FIXME: abstract this method so it loads file with the relative
    # flumotion/ path as put together in bundles,
    # and it looks for the right bundle for this file
    def loadGladeFile(self, gladeFile):
        path = os.path.join(self.view.uidir, gladeFile)
        if not os.path.exists(path):
            self.warning ("Glade file %s not found in path %s" % (
                gladeFile, path))
        wtree = gtk.glade.XML(path)
        return wtree

    ### child class methods to be overridden
    def setUIState(self, state):
        raise NotImplementedError

    def propertyChanged(self, name, value):
        """
        Override this method to be notified of component's properties that
        have changed.

        I am meant to be overridden.
        """
        self.debug("property %s changed to %r" % (name, value))

    def setup(self):
        """
        Set up the admin view so it can display nodes.
        """
        raise NotImplementedError("Child class needs to implement setup")

    def getNodes(self):
        """
        Return a dictionary of node names to admin UI nodes.
        """
        raise NotImplementedError("Child class needs to implement getNodes")

    # FIXME: deprecated
    def render(self):
        """
        Render the GTK+ admin view for this component and return the
        main widget for embedding.
        """
        raise NotImplementedError

class BaseAdminGtkNode(log.Loggable):
    """
    I am a base class for all GTK+-based Admin UI nodes.
    I am a view on a set of properties for a component.
    """

    logCategory = "admingtk"

    def __init__(self, state, admin, view):
        """
        @param state: state of component this is a UI node for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @param admin: the admin model that interfaces with the manager for us
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param view:  the GTK+ admin view we are embedded in
        @type  view:  L{flumotion.component.base.admin_gtk.BaseAdminGtk} 
        """
        self.state = state
        self.admin = admin
        self.view = view
        
    def propertyErrback(self, failure, window):
        failure.trap(errors.PropertyError)
        self.warning("%s." % failure.getErrorMessage())
        #window.error_dialog("%s." % failure.getErrorMessage())
        return None

    def setElementProperty(self, elementName, propertyName, value):
        """
        Set the given property on the element with the given name."
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

    def callRemote(self, method_name, *args, **kwargs):
        return self.admin.componentCallRemote(self.state, method_name,
                                              *args, **kwargs)
       
        
    def loadGladeFile(self, gladeFile):
        """
        Returns: a deferred returning the widget tree from the glade file.
        """
        def _getBundledFileCallback(result, gladeFile):
            path = result
            if not os.path.exists(path):
                self.warning("Glade file %s not found in path %s" % (
                    gladeFile, path))
            wtree = gtk.glade.XML(path)
            return wtree

        self.debug("requesting bundle for glade file %s" % gladeFile)
        d = self.admin.getBundledFile(gladeFile)
        d.addCallback(_getBundledFileCallback, gladeFile)
        return d

    ### child class methods to be overridden
    def setUIState(self, state):
        raise NotImplementedError

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
        raise NotImplementedError

class EffectAdminGtkNode(BaseAdminGtkNode):
    """
    I am a base class for all GTK+-based component effect Admin UI nodes.
    I am a view on a set of properties for an effect on a component.

    @ivar widget: the main widget representing this node
    @type widget: L{gtk.Widget}
    @ivar wtree:  the widget tree representation for this node
    """
    def __init__(self, state, admin, view, effectName):
        """
        @param state: state of component this is a UI for
        @type  state: L{flumotion.common.planet.AdminComponentState}
        @param admin: the admin model that interfaces with the manager for us
        @type  admin: L{flumotion.admin.admin.AdminModel}
        @param view:  the GTK+ admin view we are embedded in
        @type  view:  L{flumotion.component.base.admin_gtk.BaseAdminGtk} 
        """
        BaseAdminGtkNode.__init__(self, state, admin, view)
        self.effectName = effectName

        self.wtree = None
        self.widget = None

    def effectCallRemote(self, methodName, *args, **kwargs):
        return self.admin.componentCallRemote(self.state,
            "effect", self.effectName, methodName, *args, **kwargs)
 
