# -*- Mode: Python -*-
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
from flumotion.common import log, pygobject


# FIXME: what does this mean ?
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
# FIXME: what does this do ?
gtk.glade.set_custom_handler(flumotion_glade_custom_handler)


class GladeBacked:
    """
    Base class for objects backed by glade interface definitions.
    The glade file should have exactly one Window.

    @ivar glade_dir:      directory where the glade file is stored
    @type glade_dir:      str
    @ivar glade_file:     filename of glade file containing the interface
    @type glade_file:     str
    @ivar glade_typedict: GTK widget class name -> replacement widget class
                          see L{flumotion.ui.fgtk.WidgetMapping}
    @type glade_typedict: dict of str -> class
    @ivar widgets:        widget name -> Widget
    @type widgets:        str -> gtk.Widget
    """
    glade_dir = configure.gladedir
    glade_file = None
    glade_typedict = None
    widgets = None

    _window = None # the gtk.Window of the glade file

    def __init__(self):
        self.widgets = {}
        try:
            assert self.glade_file, "%s.glade_file should be set" % \
                self.__class__
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

        for widget in wtree.get_widget_prefix(''):
            wname = widget.get_name()
            if isinstance(widget, gtk.Window):
                assert self._window == None, \
                    "glade file %s has more than one Window" % self.glade_file
                self._window = widget
                continue

            assert not self.widgets.has_key(wname), \
                "There is already a widget called %s" % wname

            self.widgets[wname] = widget
            
        assert self._window != None, \
            "glade file %s has no Window" % self.glade_file

        # connect all signals
        wtree.signal_autoconnect(self)

class GladeWidget(gtk.VBox, GladeBacked):
    '''
    Base class for composite widgets backed by glade interface definitions.

    The Window contents will be reparented to ourselves.
    All widgets inside the Window will be available as attributes on the
    object (dashes will be replaced with underscores).
    
    Example:
    class MyWidget(GladeWidget):
        glade_file = 'my_glade_file.glade'
        ...
    gobject.type_register(MyWidget)

    Remember to chain up if you customize __init__().

    '''
    def __init__(self):
        GladeBacked.__init__(self)
        gtk.VBox.__init__(self)
            
        for name, widget in self.widgets.items():
            # translate - to _ so we can access them as attributes
            if name.find('-') > -1:
                name = "_".join(name.split('-'))
            setattr(self, name, widget)

        # we reparent the contents of the window to ourselves
        w = self._window.get_child()
        self._window.remove(w)
        self.add(w)
        self._window.destroy()
        self._window = None
pygobject.type_register(GladeWidget)

class GladeWindow(gobject.GObject, GladeBacked):
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

    @ivar window: the gtk Window
    @type window: gtk.Window
    """
    interesting_signals = ()
    window = None

    def __init__(self, parent=None):
        gobject.GObject.__init__(self)
        GladeBacked.__init__(self)

        # make public
        self.window = self._window

        if parent:
            self.window.set_transient_for(parent)

        self.__signals = {}
        for name, widget in self.widgets.iteritems():
            for prefix, signal in self.interesting_signals:
                if name.startswith(prefix):
                    hid = self.connect_signal(name, signal)
                    self.__signals[(name, signal)] = hid

        # have convenience methods acting on our window
        self.show = self.window.show
        self.hide = self.window.hide
        self.present = self.window.present

    def destroy(self):
        self.window.destroy()
        del self.window

    def connect_signal(self, widget_name, signal):
        """
        Connect a conventionally-named signal handler.

        For example:
          connect_signal('window-foo', 'delete-event')
        is equivalent to:
          proc = self.on_window_foo_delete_event
          self.widgets['window-foo'].connect('delete-event', proc)

        @param widget_name: the name of the widget
        @type  widget_name: str
        @param signal: which gobject signal to connect to
        @type  signal: str
        """
        attr = '_'.join(('on-%s-%s' % (widget_name, signal)).split('-'))
        self.log('trying to connect self.%s for widget %s::%s',
                 attr, widget_name, signal)
        proc = lambda *x: getattr(self, attr)()
        return self.widgets[widget_name].connect(signal, proc)
        
    # somewhat experimental decorator
    # this is only used by flowtester
    # FIXME: if this wants to stay a public method, it should be commented
    # and get an example so non-Andy people understand this code.
    def with_blocked_signal(self, widget_name, signal):
        w = self.widgets[widget_name]
        hid = self.__signals[(widget_name, signal)]
        def blocker(proc):
            def blocked(*args, **kwargs):
                w.handler_block(hid)
                try:
                    ret = proc(*args, **kwargs)
                finally:
                    w.handler_unblock(hid)
                return ret
            return blocked
        return blocker

    def destroy(self):
        self.window.destroy()
        del self.window

pygobject.type_register(GladeWindow)
