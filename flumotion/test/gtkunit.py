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

from twisted.internet import reactor
from twisted.trial import unittest

try:
    import gobject
    import gtk
except RuntimeError:
    os._exit(0)

_INTERVAL = 1 # in ms
if os.environ.has_key('FLU_INTERVAL'):
    _INTERVAL = int(os.environ['FLU_INTERVAL'])

_WINDOW = None
def set_window(w):
    global _WINDOW
    _WINDOW = w

_FAILED = False
def assert_not_failed():
    assert not _FAILED

def _assert(expr):
    if not expr:
        raise # to show the backtrace
    _FAILED = True

def timeout_add(proc, increase=True):
    def proc_no_return():
        try:
            proc()
        except:
            #gobject.timeout_add(0, gtk.main_quit)
            global _FAILED
            _FAILED = True
            reactor.callLater(0, os._exit, 1)
            raise
    gobject.timeout_add(timeout_add.n * _INTERVAL, proc_no_return)
    if increase:
        timeout_add.n += 1
timeout_add.n = 0
         
def find_widget(parent, name):
    if parent.get_name() == name:
        return parent
    if isinstance(parent, gtk.Container):
        for kid in parent.get_children():
            found = find_widget(kid, name)
            if found:
                return found
    return None
            
def call_now(name, method, *args, **kwargs):
    w = find_widget(_WINDOW, name)
    assert w
    m = getattr(w, method)
    return m(*args, **kwargs)


def _call(increase, name, method, *args, **kwargs):
    def check():
        call_now(name, method, *args, **kwargs)

    timeout_add(check, increase=increase)

def call(name, method, *args, **kwargs):
    """
    Call method on the widget with the given name, and given args.
    """
    _call(False, name, method, *args, **kwargs)

def call_inc(name, method, *args, **kwargs):
    """
    Like call, but also increments the timer.
    """
    _call(True, name, method, *args, **kwargs)

def assert_call_returns(name, method, val, *args, **kwargs):
    def check():
        w = find_widget(_WINDOW, name)
        assert w
        m = getattr(w, method)
        _assert(m(*args, **kwargs) == val)
    timeout_add(check)

def click(name):
    call_inc(name, 'set_relief', gtk.RELIEF_HALF)
    call_inc(name, 'set_relief', gtk.RELIEF_NORMAL)
    call_inc(name, 'emit', 'clicked')

def set_text(name, text):
    call(name, 'grab_focus')
    call_inc(name, 'delete_text', 0, -1)
    for i in range(len(text)):
        call(name, 'set_position', i)
        call(name, 'insert_text', text[i], i)
        call_inc(name, 'set_position', i + 1)

def check_text(name, text):
    assert_call_returns(name, 'get_text', text)

def set_active(name, is_active):
    call_inc(name, 'set_sensitive', False)
    call(name, 'set_sensitive', True)
    call_inc(name, 'set_active', is_active)

def pause():
    timeout_add(lambda: 0)

# FIXME: maybe move methods above to this class instead ?
class GtkTestCase(unittest.TestCase):
    def process(self):
        """
        Make sure all previous timeouts are processed, so that all state
        is updated.
        """
        timeout_add(gtk.main_quit, increase=False)
        gtk.main()

    def toggle(self, name, process=True):
        """
        toggle a gtk.ToggleButton.
        """
        is_active = call_now(name, 'get_active') 
        call_inc(name, 'set_sensitive', False)
        call(name, 'set_sensitive', True)
        call_inc(name, 'set_active', not is_active)
        if process:
            self.process()


