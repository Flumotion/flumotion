# -*- Mode: Python; fill-column: 80 -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import os
import sys

import gtk
import gtk.glade
import gobject

from flumotion.configure import configure
from flumotion.common import log, compat


# proc := module1.module2.moduleN.proc1().maybe_another_proc()
#  -> eval proc1().maybe_another_proc() in module1.module2.moduleN
def flumotion_glade_custom_handler(xml, proc, name, *args):
    def takewhile(proc, l):
        ret = []
        while l and proc(l[0]):
            ret.append(l[0])
            l.remove(l[0])
        return ret

    def parse_proc(proc):
        parts = proc.split('.')
        assert len(parts) > 1
        modparts = takewhile(str.isalnum, parts)
        assert modparts and parts
        return '.'.join(modparts), '.'.join(parts)

    module, code = parse_proc(proc)
    try:
        __import__(module)
    except Exception, e:
        msg = log.getExceptionMessage(e)
        raise RuntimeError('Failed to load module %s: %s' % (module, msg))

    try:
        w = eval(code, sys.modules[module].__dict__)
    except Exception, e:
        msg = log.getExceptionMessage(e)
        raise RuntimeError('Failed call %s in module %s: %s'
                           % (code, module, msg))
    w.set_name(name)
    w.show()
    return w
gtk.glade.set_custom_handler(flumotion_glade_custom_handler)


class GladeWidget(gtk.VBox):
    '''
    Base class for composite widgets backed by glade interface definitions.

    Example:
    class MyWidget(GladeWidget):
        glade_file = 'my_glade_file.glade'
        ...
    gobject.type_register(MyWidget)

    Remember to chain up if you customize __init__().
    '''
        
    glade_dir = configure.gladedir
    glade_file = None
    glade_typedict = None

    def __init__(self):
        gtk.VBox.__init__(self)
        try:
            assert self.glade_file
            file = os.path.join(self.glade_dir, self.glade_file)
            if self.glade_typedict:
                wtree = gtk.glade.XML(file, typedict=self.glade_typedict)
            else:
                # pygtk 2.4 doesn't like typedict={} ?
                wtree = gtk.glade.XML(file)
        except RuntimeError, e:
            msg = log.getExceptionMessage(e)
            raise RuntimeError('Failed to load file %s from directory %s: %s'
                               % (self.glade_file, self.glade_dir, msg))

        win = None
        for widget in wtree.get_widget_prefix(''):
            wname = widget.get_name()
            if isinstance(widget, gtk.Window):
                assert win == None
                win = widget
                continue
            
            if hasattr(self, wname) and getattr(self, wname):
                raise AssertionError(
                    "There is already an attribute called %s in %r" %
                    (wname, self))
            setattr(self, wname, widget)

        assert win != None
        w = win.get_child()
        win.remove(w)
        self.add(w)
        win.destroy()
        wtree.signal_autoconnect(self)
compat.type_register(GladeWidget)


class GladeWindow(gobject.GObject):
    """
    Base class for dialogs or windows backed by glade interface definitions.

    Example:
    class MyWindow(GladeWindow):
        glade_file = 'my_glade_file.glade'
        ...

    Remember to chain up if you customize __init__(). Also note that GladeWindow
    does *not* descend from GtkWindow, so you can't treat the resulting object
    as a GtkWindow. The show, hide, destroy, and present methods are provided as
    convenience wrappers.
    """

    glade_dir = configure.gladedir
    glade_file = None
    glade_typedict = None

    window = None

    def __init__(self, parent=None):
        gobject.GObject.__init__(self)
        try:
            assert self.glade_file
            file = os.path.join(self.glade_dir, self.glade_file)
            if self.glade_typedict:
                wtree = gtk.glade.XML(file, typedict=self.glade_typedict)
            else:
                # pygtk 2.4 doesn't like typedict={} ?
                wtree = gtk.glade.XML(file)
        except RuntimeError, e:
            msg = log.getExceptionMessage(e)
            raise RuntimeError('Failed to load file %s from directory %s: %s'
                               % (self.glade_file, self.glade_dir, msg))

        self.widgets = {}
        for widget in wtree.get_widget_prefix(''):
            wname = widget.get_name()
            if isinstance(widget, gtk.Window):
                assert self.window == None
                self.window = widget
                continue
            
            if wname in self.widgets:
                raise AssertionError("Two objects with same name (%s): %r %r"
                                     % (wname, self.widgets[wname], widget))
            self.widgets[wname] = widget

        if parent:
            self.window.set_transient_for(parent)

        wtree.signal_autoconnect(self)

        self.show = self.window.show
        self.hide = self.window.hide
        self.present = self.window.present

    def destroy(self):
        self.window.destroy()
        del self.window

compat.type_register(GladeWindow)
