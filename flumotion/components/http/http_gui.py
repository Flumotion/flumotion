# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import gtk

from flumotion.twisted import errors

class BaseUI:
    def __init__(self, name, admin):
        self.name = name
        self.admin = admin
        
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
        
    def setUiState(self, state):
        raise NotImplementedError
    
class HTTPStreamerUI(BaseUI):
    def error_dialog(self, message):
        print 'ERROR:', message
        
    def cb_getMimeType(self, mime, label):
        label.set_text('Mime type: %s' % mime)
        label.show()

    def setUiState(self, state):
        self.label_mime.set_text(state['mime'])
        self.label_clients.set_text(str(state['clients-connected']))
        self.label_uptime.set_text(str(state['uptime']))
        
    def render(self):
        def newRow(name):
            hbox = gtk.HBox()
            label = gtk.Label(name + ':')
            label.show()
            hbox.pack_start(label)
            label = gtk.Label()
            label.show()
            hbox.pack_start(label)
            hbox.show()
            return hbox, label
        
        vbox = gtk.VBox()
        hbox, self.label_mime = newRow('Mime')
        vbox.pack_start(hbox)
        
        hbox, self.label_clients = newRow('Clients')
        vbox.pack_start(hbox)

        hbox, self.label_uptime = newRow('Uptime')
        vbox.pack_start(hbox)

        vbox.show()

        self.callRemote('notifyState')
        
        return vbox

GUIClass = HTTPStreamerUI
