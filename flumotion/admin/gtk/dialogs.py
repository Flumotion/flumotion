# -*- Mode: Python; test-case-name: flumotion.test.test_dialogs -*-
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

from flumotion.common.pygobject import gsignal

import gtk
import gobject

class ProgressDialog(gtk.Dialog):
    def __init__(self, title, message, parent = None):
        gtk.Dialog.__init__(self, title, parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)

                                                                               
        self.label = gtk.Label(message)
        self.vbox.pack_start(self.label, True, True)
        self.bar = gtk.ProgressBar()
        self.vbox.pack_end(self.bar, True, True)
        self.active = False

    def start(self):
        "Show the dialog and start pulsating."
        self.active = True
        self.show_all()
        self.bar.pulse()
        self.timeout_cb = gobject.timeout_add(200, self._pulse)

    def stop(self):
        "Remove the dialog and stop pulsating."
        self.active = False

    def message(self, message):
        "Set the message on the dialog."
        self.label.set_text(message)

    def _pulse(self):
        if not self.active:
            # we were disabled, so stop pulsating
            return False
        self.bar.pulse()
        return True

class ErrorDialog(gtk.MessageDialog):
    def __init__(self, message, parent=None, close_on_response=True):
        gtk.MessageDialog.__init__(self, parent, gtk.DIALOG_MODAL,
            gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, message)
        if close_on_response:
            self.connect("response", lambda self, response: self.hide())

class PropertyChangeDialog(gtk.Dialog):
    """
    I am a dialog to get and set GStreamer element properties on a component.
    """

    gsignal('set', str, str, object)
    gsignal('get', str, str)
    
    RESPONSE_FETCH = 0
    
    def __init__(self, name, parent):
        title = "Change element property on '%s'" % name
        gtk.Dialog.__init__(self, title, parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        self.connect('response', self.response_cb)
        self._close = self.add_button('Close', gtk.RESPONSE_CLOSE)
        self._set = self.add_button('Set', gtk.RESPONSE_APPLY)
        self._fetch = self.add_button('Fetch current', self.RESPONSE_FETCH)

        hbox = gtk.HBox()
        hbox.show()
        
        label = gtk.Label('Element')
        label.show()
        hbox.pack_start(label, False, False)
        self.element_combo = gtk.ComboBox()
        self.element_entry = gtk.Entry()
        self.element_entry.show()
        hbox.pack_start(self.element_entry, False, False)

        label = gtk.Label('Property')
        label.show()
        hbox.pack_start(label, False, False)
        self.property_entry = gtk.Entry()
        self.property_entry.show()
        hbox.pack_start(self.property_entry, False, False)
        
        label = gtk.Label('Value')
        label.show()
        hbox.pack_start(label, False, False)
        self.value_entry = gtk.Entry()
        self.value_entry.show()
        hbox.pack_start(self.value_entry, False, False)

        self.vbox.pack_start(hbox)
        
    def response_cb(self, dialog, response):
        if response == gtk.RESPONSE_APPLY:
            self.emit('set', self.element_entry.get_text(),
                      self.property_entry.get_text(),
                      self.value_entry.get_text())
        elif response == self.RESPONSE_FETCH:
            self.emit('get', self.element_entry.get_text(),
                      self.property_entry.get_text())
        elif response == gtk.RESPONSE_CLOSE:
            dialog.hide()

    def update_value_entry(self, value):
        self.value_entry.set_text(str(value))
    
gobject.type_register(PropertyChangeDialog)
