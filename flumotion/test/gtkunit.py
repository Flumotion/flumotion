# -*- Mode: Python; test-case-name: flumotion.test.test_greeter -*-
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

try:
    import gobject
    import gtk
except RuntimeError:
    import os
    os._exit(0)

_INTERVAL = 10 # in ms

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
    FAILED = True

def timeout_add(proc):
    def proc_no_return():
        proc()
    gobject.timeout_add(timeout_add.n * _INTERVAL, proc_no_return)
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
            
def call(name, method, *args, **kwargs):
    def check():
        w = find_widget(_WINDOW, name)
        assert w
        m = getattr(w, method)
        m(*args, **kwargs)
    timeout_add(check)

def assert_call_returns(name, method, val, *args, **kwargs):
    def check():
        w = find_widget(_WINDOW, name)
        assert w
        m = getattr(w, method)
        _assert(m(*args, **kwargs) == val)
    timeout_add(check)
