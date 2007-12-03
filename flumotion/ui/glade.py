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
from gtk import glade
import gobject
from twisted.python.reflect import namedAny

from flumotion.configure import configure
from flumotion.common import log, pygobject


def _unbrokenNamedAny(qual):
    # ihooks breaks namedAny, so split up by module, attribute
    module_name, attribute = qual.rsplit(".", 1)
    module = namedAny(module_name)
    return getattr(module, attribute, None)

def _flumotion_glade_custom_handler(xml, proc, name, *args):
    widget_class = _unbrokenNamedAny(proc)
    if widget_class is None:
        mod, attr = proc.rsplit(".", 1)
        raise RuntimeError(
            "There is no widget called %r in module %s" % (
            attr, mod))

    widget = widget_class()
    widget.set_name(name)

    # Normal properties are not parsed for Custom widgets,
    # showing all non-window ones by default is probably a good idea
    if not isinstance(widget, gtk.Window):
        widget.show()

    return widget

glade.set_custom_handler(_flumotion_glade_custom_handler)


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
            file_path = os.path.join(self.glade_dir, self.glade_file)
            if self.glade_typedict:
                wtree = glade.XML(file_path, typedict=self.glade_typedict)
            else:
                # pygtk 2.4 doesn't like typedict={} ?
                wtree = glade.XML(file_path)
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

    Example::
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

    Example::
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
                    hid = self._connect_signal(name, signal)
                    self.__signals[(name, signal)] = hid

        # have convenience methods acting on our window
        self.show = self.window.show
        self.hide = self.window.hide
        self.present = self.window.present

    def destroy(self):
        self.window.destroy()
        del self.window

    def _connect_signal(self, widget_name, signal):
        """
        Connect a conventionally-named signal handler.

        For example::
          connect_signal('window-foo', 'delete-event')

        is equivalent to::
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

pygobject.type_register(GladeWindow)
