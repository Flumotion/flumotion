# -*- Mode: Python; test-case-name: flumotion.test.test_greeter -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

import os

import gobject
import gtk
from twisted.internet import reactor

from flumotion.common import testsuite

_INTERVAL = 1 # in ms
if 'FLU_INTERVAL' in os.environ:
    _INTERVAL = int(os.environ['FLU_INTERVAL'])


class UITestCase(testsuite.TestCase):

    # TestCase

    def setUp(self):
        self._window = None
        self._n = 0

    # Public

    def setWindow(self, window):
        self._window = window

    def refreshUI(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def assertCallReturns(self, name, method, val, *args, **kwargs):
        def check():
            w = self._findWidget(self._window, name)
            assert w
            m = getattr(w, method)
            self.assertEquals(m(*args, **kwargs), val)
        self._timeoutAdd(check)

    def assertSensitive(self, name, s):
        self.assertCallReturns(name, 'get_property', s, 'sensitive')

    def click(self, name):
        self._callInc(name, 'set_relief', gtk.RELIEF_HALF)
        self._callInc(name, 'set_relief', gtk.RELIEF_NORMAL)
        self._callInc(name, 'emit', 'clicked')

    def inactivate(self, name):
        w = self._findWidget(self._window, name)
        w.set_active(False)

    def activate(self, name):
        w = self._findWidget(self._window, name)
        w.set_active(True)

    def setText(self, name, text):
        self._call(name, 'grab_focus')
        self._callInc(name, 'delete_text', 0, -1)
        for i in range(len(text)):
            self._call(name, 'set_position', i)
            self._call(name, 'insert_text', text[i], i)
            self._callInc(name, 'set_position', i + 1)

    def checkText(self, name, text):
        self.assertCallReturns(name, 'get_text', text)

    def setActive(self, name, is_active):
        self._callInc(name, 'set_sensitive', False)
        self._call(name, 'set_sensitive', True)
        self._callInc(name, 'set_active', is_active)

    def setWidget(self, widget):
        self.window = gtk.Window()
        self.widget = widget
        self.setWindow(self.window)
        widget.reparent(self.window)
        self.window.show_all()
        self._pause()

    def toggle(self, name, process=True):
        isActive = self._callNow(name, 'get_active')
        self._callInc(name, 'set_sensitive', False)
        self._call(name, 'set_sensitive', True)
        self._callInc(name, 'set_active', not isActive)
        if process:
            self._process()

    # Private

    def _pause(self):
        self._timeoutAdd(lambda: 0)

    def _timeoutAdd(self, proc, increase=True):
        def proc_no_return():
            try:
                proc()
            except:
                #gobject.timeoutAdd(0, gtk.main_quit)
                reactor.callLater(0, os._exit, 1)
                raise
        gobject.timeout_add(self._n * _INTERVAL, proc_no_return)
        if increase:
            self._n += 1

    def _findWidget(self, parent, name):
        if parent.get_name() == name:
            return parent
        if isinstance(parent, gtk.Container):
            for child in parent.get_children():
                found = self._findWidget(child, name)
                if found:
                    return found
        return None

    def _process(self):
        """
        Make sure all previous timeouts are processed, so that all state
        is updated.
        """
        self._timeoutAdd(gtk.main_quit, increase=False)
        gtk.main()

    def _callNow(self, name, method, *args, **kwargs):
        w = self._findWidget(self._window, name)
        assert w, "Couldn't find widget %s" % name
        m = getattr(w, method)
        return m(*args, **kwargs)

    def _batchCall(self, increase, name, method, *args, **kwargs):
        def check():
            self._callNow(name, method, *args, **kwargs)

        self._timeoutAdd(check, increase=increase)

    def _call(self, name, method, *args, **kwargs):
        """
        Call method on the widget with the given name, and given args.
        """
        self._batchCall(False, name, method, *args, **kwargs)

    def _callInc(self, name, method, *args, **kwargs):
        """
        Like call, but also increments the timer.
        """
        self._batchCall(True, name, method, *args, **kwargs)


