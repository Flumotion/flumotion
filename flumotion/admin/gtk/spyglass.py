# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/admin/spyglass.py: MVC for spyglass
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

# FIXME: moving this down causes errors
from flumotion.common import log

import gobject
import gst
import gst.interfaces
import gtk
import gtk.glade

from flumotion.configure import configure
from flumotion.utils.gstutils import gsignal

import os

if gtk.pygtk_version < (2,3,91):
    raise SystemExit, "PyGTK 2.3.91 or higher required"

def _debug(*args):
    log.debug('spyglass', ' '.join(args))

# only Controller is to be shown in epydoc
__all__ = ('Controller', )
    
class Controller(gobject.GObject):
    """
    Controller for a spyglass, used for viewing a video feed.
    The controller's model takes a raw video feed as accepted by ximagesink.
    """
    # FIXME: decide on a good name for prepared that says "you can do stuff with me
    # now"
    gsignal('prepared')
    gsignal('focus-changed', object)
    
    def __init__(self):
        """
        Create a new spyglass controller.
        The spyglass controller needs to be prepared.
        """
        self.__gobject_init__()
        self.view = View()
        self.model = Model()

    ### public methods

    def prepare(self):
        """
        Prepares the controller.
        Returns immediately.
        Emits 'prepared' signal when it is done preparing.
        """
        self.view.connect('have-xid', self._view_have_xid_cb)
        self.view.connect('focus-changed', self._view_focus_changed_cb)
        # the view's prepare is synchronous for now
        self.view.prepare()
        # the model doesn't currently have a prepare

    def add_focus(self, key, description):
        """
        Adds a focus point for the spyglass.
        @type key: C{object}
        @param key: the key for this focus point.
        @type description: C{string}
        @param description: the description for the focus point in the view.
        """
        self.view.add_focus(key, description)

    def set_focus(self, key):
        """
        Sets the focus point in the view given by the key.
        @type key: C{object}
        @param key: the key for the focus point.
        """
        self.view.set_focus(key)

    ### callbacks

    def _view_have_xid_cb(self, view, xid):
        _debug("_view_have_xid_cb: have xid %d" % xid)
        self.model.set_xid(xid)
        self.emit('prepared')

    def _view_focus_changed_cb(self, view, key):
        self.emit('focus-changed', key)

class View(gobject.GObject):
    gsignal('have-xid', long)
    gsignal('focus-changed' , object)

    def __init__(self):
        """
        Construct a new Spyglass View.
        """
        self.__gobject_init__()
        self._gladefile = os.path.join(configure.gladedir, 'spyglass.glade')
        self._glade = gtk.glade.XML(self._gladefile, "spyglass-widget")
        self._widget = self._glade.get_widget("spyglass-widget")
        self._combo = self._glade.get_widget("spyglass-combo")

    def prepare(self):
        # create an empty tree model for the combobox and set it there
        self._focus_model = gtk.ListStore(str, object)
        # hash for key -> model row mapping for quick set_focus lookup
        self._focus_key = {}
        self._combo.set_model(self._focus_model)
        self._combo.connect("changed", self.view_combo_changed_cb)

        # connect realize callback to drawing area so we know when to get
        # the xid
        area = self._glade.get_widget("spyglass-area")
        assert(area)
        self._expose_id = area.connect("expose-event", self.view_exposed_cb)

    def get_widget(self):
        return self._widget

    def add_focus(self, key, description):
        self._focus_key[key] = len(self._focus_model)
        self._focus_model.append((description, key))

    def set_focus(self, key):
        self._combo.set_active(self._focus_key[key])

    ### callbacks

    def view_combo_changed_cb(self, combo):
        iter = combo.get_active_iter()
        row = self._focus_model[combo.get_active()]
        key = row[1]
        self.emit('focus-changed', key)
        
    def view_exposed_cb(self, widget, event):
        'store our xid now that we are exposed'
        widget.disconnect(self._expose_id)
        self._xid = widget.window.xid 
        _debug("view_exposed_cb, got xid %d" % self._xid)
        self.emit('have-xid', self._xid)

class Model:
    def __init__(self):
        self._sink = gst.Element('ximagesink')

    def get_element(self):
        'Gets the element we should link and put in our main bin'
        return self._sink

    def set_xid(self, xid):
        # use of long is due to a pygtk bug
        self._sink.set_xwindow_id(long(xid))
        
# register our types globally
gobject.type_register(View)
gobject.type_register(Controller)

if __name__ == '__main__':
    def controller_prepared_cb(controller, thread):
        # we can set stuff to playing now
        _debug("setting thread to PLAYING")
        thread.set_state(gst.STATE_PLAYING)

    def controller_focus_changed_cb(controller, key, src):
        _debug("focus changed to key %s" % key)
        src.set_property('pattern', key)

    _debug("testing")

    # create fake toplevel model
    thread = gst.Thread()
    src = gst.Element('videotestsrc')
    csp = gst.Element('ffmpegcolorspace')

    # create our controller
    controller = Controller()
    controller.connect("prepared", controller_prepared_cb, thread)
    controller.connect("focus-changed", controller_focus_changed_cb, src)
    controller.prepare()

    # add possible spyglass focuses
    # we "fake" spyglass focuses by just changing the pattern on the
    # same videotestsrc, using the enum value as the key
    controller.add_focus(1, 'Snow source')
    controller.add_focus(0, 'Snow embedded in test signal')
    controller.add_focus(2, 'Snow in the dark')
    # set to smpte by default
    controller.set_focus(2)

    # embed the view in our fake toplevel view
    window = gtk.Window()
    window.connect('destroy', gtk.main_quit)
    window.add(controller.view.get_widget())
    window.show_all()

    # embed the model in our fake toplevel model
    sink = controller.model.get_element()
    prev = None
    for e in (src, csp, sink):
        thread.add(e)
        if prev: prev.link(e)
        prev = e
    
    _debug("going into gtk.main")
    gtk.main()
