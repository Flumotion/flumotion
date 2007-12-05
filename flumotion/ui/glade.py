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

__version__ = "$Rev$"

import os

import gtk
from gtk import glade
import gobject
from kiwi.environ import environ
from kiwi.ui import views
from kiwi.ui.delegates import GladeDelegate
from twisted.python.reflect import namedAny

from flumotion.configure import configure

# FIXME: Move to kiwi initialization
environ.add_resource('glade', configure.gladedir)

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


# Kiwi monkey patch, allows us to specify a
# glade_typedict on the View.
class FluLibgladeWidgetTree(glade.XML):
    def __init__(self, view, gladefile, domain=None):
        self._view = view
        glade.XML.__init__(self, gladefile, domain,
                           typedict=view.glade_typedict or {})

        for widget in self.get_widget_prefix(''):
            setattr(self._view, widget.get_name(), widget)

    def get_widget(self, name):
        name = name.replace('.', '_')
        widget = glade.XML.get_widget(self, name)
        if widget is None:
            raise AttributeError(
                  "Widget %s not found in view %s" % (name, self._view))
        return widget

    def get_widgets(self):
        return self.get_widget_prefix('')

    def get_sizegroups(self):
        return []

def _open_glade(view, gladefile, domain):
    if not gladefile:
        raise ValueError("A gladefile wasn't provided.")
    elif not isinstance(gladefile, basestring):
        raise TypeError(
              "gladefile should be a string, found %s" % type(gladefile))

    if not '/' in gladefile:
        filename = os.path.splitext(os.path.basename(gladefile))[0]
        gladefile = environ.find_resource("glade", filename + '.glade')
    return FluLibgladeWidgetTree(view, gladefile, domain)

views._open_glade = _open_glade

class GladeBacked(GladeDelegate):
    """
    Base class for objects backed by glade interface definitions.
    The glade file should have exactly one Window.

    @ivar glade_file:     filename of glade file containing the interface
    @type glade_file:     str
    @ivar glade_typedict: GTK widget class name -> replacement widget class
                          see L{flumotion.ui.fgtk.WidgetMapping}
    @type glade_typedict: dict of str -> class
    @ivar widgets:        widget name -> Widget
    @type widgets:        str -> gtk.Widget
    """
    glade_file = None
    glade_typedict = None
    toplevel_name = "window1"

    _window = None # the gtk.Window of the glade file

    def __init__(self):
        GladeDelegate.__init__(self, gladefile=self.glade_file)

        wtree = self.get_glade_adaptor()
        wtree.signal_autoconnect(self)
        self.widgets = {}
        for widget in wtree.get_widgets():
            self.widgets[widget.get_name()] = widget
        self._window = self.widgets[self.toplevel_name]


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

gobject.type_register(GladeWidget)


class GladeWindow(GladeBacked):
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
    window = None

    def __init__(self, parent=None):
        GladeBacked.__init__(self)

        # make public
        self.window = self._window

        if parent:
            self.window.set_transient_for(parent)

        # have convenience methods acting on our window
        self.show = self.window.show
        self.hide = self.window.hide
        self.present = self.window.present

    def destroy(self):
        self.window.destroy()
        del self.window

gobject.type_register(GladeWindow)
