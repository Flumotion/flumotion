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

from twisted.trial import unittest

import common

import gobject
import gtk

from flumotion.admin.gtk import dialogs

INTERVAL = 100 # in ms

class TestProgressDialog(unittest.TestCase):
    def setUp(self):
        self.window = gtk.Window()

    def tearDown(self):
        self.window.destroy()

    def testDialog(self):
        dialog = dialogs.ProgressDialog("I am busy",
            'Doing lots of complicated stuff', self.window)
        dialog.start()

        def stop(dialog):
            dialog.stop()
            gtk.main_quit()
            
        gobject.timeout_add(1 * INTERVAL,
            lambda dialog: dialog.message('Step 1'), dialog)
        gobject.timeout_add(2 * INTERVAL,
            lambda dialog: dialog.message(
            'Step 2 but with a lot longer text so we test shrinking'), dialog)
        gobject.timeout_add(3 * INTERVAL,
            lambda dialog: dialog.message('Step 3'), dialog)
        gobject.timeout_add(5 * INTERVAL, stop, dialog)
        gtk.main()

class TestPropertyChangeDialog(unittest.TestCase):
    def setUp(self):
        self.window = gtk.Window()

    def tearDown(self):
        self.window.destroy()

    def testDialog(self):
        dialog = dialogs.PropertyChangeDialog("element", self.window)
        dialog.connect('get', self.get_cb)
        dialog.connect('set', self.set_cb)
        dialog.show_all()
        
        dialog.element_entry.set_text('fakesrc')
        dialog.property_entry.set_text('silent')
        gobject.timeout_add(1 * INTERVAL,
            lambda b: b.emit('clicked'), dialog._fetch)
        gtk.main()

        # make sure it was hidden
        self.failUnlessEqual(dialog.get_property('visible'), gtk.FALSE)

    def get_cb(self, dialog, element, property):
        self.failUnlessEqual(dialog.get_property('visible'), gtk.TRUE)

        self.failUnlessEqual(element, 'fakesrc')
        self.failUnlessEqual(property, 'silent')
        dialog.update_value_entry(gtk.FALSE)
        dialog.value_entry.set_text('True')
        dialog._set.emit('clicked')

    def set_cb(self, dialog, element, property, value):
        self.failUnlessEqual(element, 'fakesrc')
        self.failUnlessEqual(property, 'silent')
        # FIXME: should be possible to do gtk.TRUE
        self.failUnlessEqual(value, 'True')
        dialog._close.emit('clicked')
        gtk.main_quit()
 
class TestErrorDialog(unittest.TestCase):
    def setUp(self):
        self.window = gtk.Window()

    def tearDown(self):
        self.window.destroy()

    def testDialogMain(self):
        dialog = dialogs.ErrorDialog("I am a test error message", self.window)
        self.failUnlessEqual(dialog.get_property('visible'), gtk.FALSE)
        dialog.show_all()
        self.failUnlessEqual(dialog.get_property('visible'), gtk.TRUE)
        
        # find the button and "click" it
        hbox = dialog.action_area
        list = hbox.get_children()
        button = list[0]
        self.failUnless(isinstance(button, gtk.Button))
        
        gobject.timeout_add(1 * INTERVAL, lambda b: b.emit('clicked'), button)
        dialog.connect('unmap', lambda w: gtk.main_quit())
        
        gtk.main()
        
        self.failUnlessEqual(dialog.get_property('visible'), gtk.FALSE)

    def testDialogRun(self):
        dialog = dialogs.ErrorDialog("I am a test error message", self.window)
        self.failUnlessEqual(dialog.get_property('visible'), gtk.FALSE)
        dialog.show_all()
        self.failUnlessEqual(dialog.get_property('visible'), gtk.TRUE)
        
        # find the button and "click" it
        hbox = dialog.action_area
        list = hbox.get_children()
        button = list[0]
        self.failUnless(isinstance(button, gtk.Button))
        
        gobject.timeout_add(1 * INTERVAL, lambda b: b.emit('clicked'), button)
        dialog.run()
        
        self.failUnlessEqual(dialog.get_property('visible'), gtk.FALSE)
   
