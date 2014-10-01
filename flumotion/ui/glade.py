# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.
import os

import gtk
from gtk import glade
import gobject

#from kiwi.environ import environ
#from kiwi.ui.delegates import GladeDelegate

from twisted.python.reflect import namedAny

from flumotion.common.pygobject import gsignal
from flumotion.configure import configure
from flumotion.ui.kiwipatches import install_patches, FluLibgladeWidgetTree

__version__ = "$Rev$"

# FIXME: Move to kiwi initialization
#environ.add_resource('glade', configure.gladedir)

install_patches()


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


class GladeBacked(gobject.GObject):
    """
    Base class for objects backed by glade interface definitions.
    The glade file should have exactly one Window.

    @ivar gladeFile:     filename of glade file containing the interface
    @type gladeFile:     str
    @ivar gladeTypedict: GTK widget class name -> replacement widget class
                          see L{flumotion.ui.fgtk.ProxyWidgetMapping}
    @type gladeTypedict: dict of str -> class
    @ivar widgets:        widget name -> Widget
    @type widgets:        str -> gtk.Widget
    """
    gladeFile = None
    gladeTypedict = None
    toplevel_name = "window1"

    _window = None # the gtk.Window of the glade file

    def __init__(self):
        #GladeDelegate.__init__(self, gladefile=self.gladeFile)
        gobject.GObject.__init__(self)
        # The following code has already been monkeypatched in kiwipatches.py
        wtree = self.get_glade_adaptor()
        wtree.signal_autoconnect(self)
        self.widgets = {}
        for widget in wtree.get_widgets():
            print("Parsing widget tree, widget is: %s" % widget.get_name())
            self.widgets[widget.get_name()] = widget
        self._window = self.widgets[self.toplevel_name]


    def get_glade_adaptor(self):
        """ 
            Port the monkeypatched code from kiwi patches! 
            Change this class to inherit from object....
            Remove the kiwi imports.
            Watch the errors fly.
            This step validates the gladefile.... Will be runtime error
            aspect orientated programming, DI, ....shudder....

        """
        if not self.gladeFile:
            raise ValueError("A gladefile wasn't provided.")
        elif not isinstance(self.gladeFile, basestring):
            raise TypeError(
                  "gladefile should be a string, found %s" % type(self.gladeFile))

        if not os.path.sep in self.gladeFile:
            glade_filename = os.path.splitext(os.path.basename(self.gladeFile))[0]
            self.gladeFile = os.path.join(configure.gladedir, glade_filename + '.glade')
        else:
            # environ.find_resources raises EnvironmentError if the file
            # is not found, do the same here.
            if not os.path.exists(self.gladeFile):
                raise EnvironmentError("glade file %s does not exist" % (
                    self.gladeFile, ))
        domain = "" # Translation domain, empty string means default
        return FluLibgladeWidgetTree(self, self.gladeFile, self.toplevel_name, domain)


class GladeWidget(gtk.VBox, GladeBacked):
    '''
    Base class for composite widgets backed by glade interface definitions.

    The Window contents will be reparented to ourselves.
    All widgets inside the Window will be available as attributes on the
    object (dashes will be replaced with underscores).

    Example::
      class MyWidget(GladeWidget):
          gladeFile = 'my_gladeFile.glade'
          ...
      gobject.type_register(MyWidget)

    Remember to chain up if you customize __init__().

    '''

    gsignal('validation-changed', bool)

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
          gladeFile = 'my_gladeFile.glade'
          ...

    Remember to chain up if you customize __init__(). Also note that
    GladeWindow does *not* descend from GtkWindow, so you can't treat the
    resulting object as a GtkWindow. The show, hide, destroy, and present
    methods are provided as convenience wrappers.

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
            self.window.set_modal(True)

        # have convenience methods acting on our window
        self.show = self.window.show
        self.hide = self.window.hide
        self.present = self.window.present
        #self.connect = self.window.connect

    def destroy(self):
        self.window.destroy()
        del self.window

gobject.type_register(GladeWindow)
