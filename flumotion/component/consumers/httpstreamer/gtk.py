# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/consumer/httpstreamer/gtk.py
# admin client-side code for httpstreamer
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

import gtk

from flumotion.common import errors

### this will probably end up being shared
### maybe rename to Gtk instead of UI ?
class BaseUI:
    def __init__(self, name, admin, view):
        self.name = name
        self.admin = admin
        self.view = view
        
    def propertyErrback(self, failure, window):
        failure.trap(errors.PropertyError)
        window.error_dialog("%s." % failure.getErrorMessage())
        return None

    def setElementProperty(self, element, property, value):
        cb = self.admin.setProperty(self.name, element, property, value)
        cb.addErrback(self.propertyErrback, self)
    
    def getElementProperty(self, func, element, property):
        cb = self.admin.getProperty(self.name, element, property)
        cb.addCallback(func)
        cb.addErrback(self.propertyErrback, self)

    def callRemote(self, method_name, *args, **kwargs):
        return self.admin.callComponentRemote(self.name, method_name,
                                              *args, **kwargs)
        
    def setUIState(self, state):
        raise NotImplementedError

    def loadGladeFile(self, glade_file):
        path = os.path.join(self.view.uidir, glade_file)
        wtree = gtk.glade.XML(path)
        return wtree
        
class HTTPStreamerUI(BaseUI):
    #def __init__(self, name, admin, view):
    #    self.labels = {}
        # FIXME: Johan, this doesn't work, BaseUI is not defined
        #BaseUI.__init__(self, name, admin, view)
        
    def error_dialog(self, message):
        # FIXME: dialogize
        print 'ERROR:', message
        
    def cb_getMimeType(self, mime, label):
        label.set_text('Mime type: %s' % mime)
        label.show()

    def setUIState(self, state):
        self.updateLabels(state)
        if not self.shown:
            self.shown = True
            self.statistics.show_all()
        
    def registerLabel(self, name):
        #widgetname = name.replace('-', '_')
        #FIXME: make object member directly
        widget = self.wtree.get_widget('label-' + name)
        if widget:
            self.labels[name] = widget
        else:
            print "FIXME: no widget %s" % name

    def hideLabels(self):
        for name in self.labels.keys():
            self.labels[name].hide()

    def updateLabels(self, state):
        for name in self.labels.keys():
            text = state[name]
            if text is None:
                text = ''
            self.labels[name].set_text(text)
        
    def render(self):
        self.wtree = self.loadGladeFile('http.glade')
        self.labels = {}
        self.statistics = self.wtree.get_widget('statistics-widget')
        for type in ('uptime', 'mime', 'bitrate', 'totalbytes'):
            self.registerLabel('stream-' + type)
        for type in ('current', 'average', 'max', 'peak', 'peak-time'):
            self.registerLabel('clients-' + type)
        for type in ('bitrate', 'totalbytes'):
            self.registerLabel('consumption-' + type)

        self.callRemote('notifyState')
        self.shown = False
        return self.statistics

GUIClass = HTTPStreamerUI
