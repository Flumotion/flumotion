# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/base/admin/gtk.py
# base component admin client-side code
# 
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
    I am a base class for all GTK+-based Admin UI parts.
    """

    logCategory = "admingtk"
    
    def __init__(self, name, admin, view):
        """
        @type  name:  string
        @param name:  name of the component this is a UI for
        @type  admin: L{flumotion.admin.AdminModel}
        @param admin: the admin model that interfaces with the manager for us
        @type  view:   
        @param view:  the toolkit view we are embedded in
        """
        self.name = name
        self.admin = admin
        self.view = view
        
    def propertyErrback(self, failure, window):
        failure.trap(errors.PropertyError)
        self.warning("%s." % failure.getErrorMessage())
        #window.error_dialog("%s." % failure.getErrorMessage())
        return None

    def setElementProperty(self, elementName, propertyName, value):
        d = self.admin.setProperty(self.name, elementName, propertyName, value)
        d.addErrback(self.propertyErrback, self)
        return d
    
    def getElementProperty(self, elementName, propertyName):
        """
        Get the value given property of the element with the given name.
        
        Returns: L{twisted.internet.defer.Deferred} returning the value.
        """
        d = self.admin.getProperty(self.name, elementName, propertyName)
        d.addErrback(self.propertyErrback, self)
        return d

    def callRemote(self, method_name, *args, **kwargs):
        return self.admin.componentCallRemote(self.name, method_name,
                                              *args, **kwargs)
        
    def setUIState(self, state):
        raise NotImplementedError

    # FIXME: abstract this method so it loads file with the relative
    # flumotion/ path as put together in bundles,
    # and it looks for the right bundle for this file
    def loadGladeFile(self, glade_file):
        path = os.path.join(self.view.uidir, glade_file)
        wtree = gtk.glade.XML(path)
        return wtree

    def propertyChanged(self, name, value):
        """
        I am meant to be overridden.
        """
        self.debug("pattern %s changed to %r" % (name, value))
