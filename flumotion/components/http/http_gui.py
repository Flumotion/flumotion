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
        
    def propertyErrback(failure, window):
        failure.trap(errors.PropertyError)
        window.error_dialog("%s." % failure.getErrorMessage())
        return None

    def setElementProperty(self, element, property, value):
        cb = self.admin.setProperty(self.name, element, property, value)
        cb.addErrback(self.propertyErrback, self)
    
    def getElementProperty(self, func, element, property, value):
        cb = self.admin.getProperty(self.name, element, property, value)
        cb.addCallback(func)
        cb.addErrback(self.propertyErrback, self)
    
class HTTPStreamerUI(BaseUI):
    def button_click_cb(self, button):
        def getReturnValue(value):
            
        self.getElementProperty(getReturnValue,
                                'foo', 'bar', 'baz')
        
    def render(self):
        self.getElementProperty('foo', 'bar', 'baz')

        button = gtk.Button('Click me')
        button.connect('clicked', self.button_click_cb)
        button.show()
        return button

GUIClass = HTTPStreamerUI
