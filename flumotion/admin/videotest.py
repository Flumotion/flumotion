# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
#
# flumotion/admin/videotest.py: MVC for video test producer
#
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

# FIXME: moving this down causes errors
import flumotion.utils.log

import gobject
import gst
import gst.interfaces
import gtk
import gtk.glade

import flumotion.config

import os

if gtk.pygtk_version < (2,3,91):
   raise SystemExit, "PyGTK 2.3.91 or higher required"

def _debug(*args):
    flumotion.utils.log.debug('videotest', ' '.join(args))

# only Controller is to be shown in epydoc
__all__ = ('Controller', )
    
class Controller(gobject.GObject):
    '''
    Controller for a video test producer, used to generate a video test feed.
    The controller's model produces a raw video test feed using videotestsrc.
    '''
# FIXME: decide on a good name for prepared that says "you can do stuff with me
# now"
    __gsignals__ = {
        'prepared': (gobject.SIGNAL_RUN_FIRST, None, ()),
    }
    def __init__(self):
        """
        Create a new video test controller.
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
        # the view's prepare is synchronous for now
        self.view.prepare()
        self.view.connect('pattern-changed', self.view_pattern_changed_cb)
        # the model doesn't currently have a prepare
        self.view.add_pattern("SMPTE")
        self.view.add_pattern("Snow")
        self.view.add_pattern("0% Black")
        self.view.set_pattern(1)

    ### callbacks
    def view_pattern_changed_cb(self, view, index):
        _debug("pattern changed to index %d" % index)
        self.model.set_pattern(index)

class View(gobject.GObject):
    __gsignals__ = {
        'width-changed': (gobject.SIGNAL_RUN_FIRST, None, (int, )),
        'height-changed': (gobject.SIGNAL_RUN_FIRST, None, (int, )),
        'pattern-changed': (gobject.SIGNAL_RUN_FIRST, None, (int, )),
    }

    def __init__(self):
        """
        Construct a new videotest View.
        """
        self.__gobject_init__()
        self._gladefile = os.path.join(flumotion.config.uidir, 'videotest.glade')
        self._glade = gtk.glade.XML(self._gladefile, "videotest-widget")
        self._widget = self._glade.get_widget("videotest-widget")

    def prepare(self):
        # connect callbacks
        w = self._glade.get_widget("width-button")
        w.connect("value-changed", self.width_changed_cb)
        w = self._glade.get_widget("height-button")
        w.connect("value-changed", self.height_changed_cb)
        w = self._glade.get_widget("pattern-combo")
        self._pattern_combo = w
        self._pattern_model = gtk.ListStore(str)
        w.set_model(self._pattern_model)
        w.connect("changed", self.pattern_changed_cb)

    def get_widget(self):
        return self._widget

    def add_pattern(self, description):
        'add a pattern description to the pattern combobox'
        # FIXME: for now we don't even store enum keys, which we might want
        # to do if they're added in a different order or not always start
        # at 0
        self._pattern_model.append((description, ))

    def set_pattern(self, index):
        self._pattern_combo.set_active(index)

    ### callbacks

    def width_changed_cb(self, widget):
        width = widget.get_value()
        self.emit('width-changed', width)
    def height_changed_cb(self, widget):
        height = widget.get_value()
        self.emit('height-changed', height)
    def pattern_changed_cb(self, widget):
        index = widget.get_active()
        self.emit('pattern-changed', index)

class Model:
    def __init__(self):
        self._src = gst.Element('videotestsrc')
        self._caps = gst.caps_from_string('video/x-raw-rgb,width=320,height=240,framerate=25.0')

    def get_element(self):
        'Gets the element we should link and put in our main bin'
        return self._src
    def get_caps(self):
        'Gets the caps that should be used as filter'
        return self._caps
    def set_pattern(self, pattern):
        'Sets the pattern enum on videotestsrc to the given pattern enum value'
        self._src.set_property("pattern", pattern)

# register our types globally
gobject.type_register(View)
gobject.type_register(Controller)

if __name__ == '__main__':
    exposed_cb_id = -1
    def area_exposed_cb(widget, event, thread, sink):
        'drawing area shown, get xid and start streaming'
        xid = widget.window.xid
        _debug("area exposed, xid is %d" % xid)
        sink.set_xwindow_id(xid)
        thread.set_state(gst.STATE_PLAYING)
        widget.disconnect(exposed_cb_id)

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
    csp = gst.Element('ffmpegcolorspace')
    sink = gst.Element('ximagesink')

    # create our controller
    controller = Controller()
    controller.connect("prepared", controller_prepared_cb, thread)
    controller.prepare()

    # embed the view in our fake toplevel view
    window = gtk.Window()
    window.connect('destroy', gtk.main_quit)
    box = gtk.HBox(gtk.FALSE, 2)
    box.add(controller.view.get_widget())
    area = gtk.DrawingArea()
    area.set_size_request(320, 240)
    exposed_cb_id = area.connect('expose-event', area_exposed_cb, thread, sink)
    box.add(area)
    window.add(box)
    window.show_all()
    
    # embed the model in our fake toplevel model
    src = controller.model.get_element()
    prev = None
    for e in (src, csp, sink):
        thread.add(e)
        if prev: prev.link(e)
        prev = e

    _debug("going into gtk.main")
    gtk.main()
