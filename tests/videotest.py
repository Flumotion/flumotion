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
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

# FIXME: moving this down causes errors
from flumotion.common import log, pygobject

import os
import string

# johan says modules should not do this, only apps
import pygtk
pygtk.require('2.0')

import gobject
gobject.threads_init()
import gst
import gst.interfaces
import gtk
import gtk.glade

from flumotion.configure import configure
from flumotion.common.pygobject import gsignal


if gtk.pygtk_version < (2, 3, 96):
    raise SystemExit("PyGTK 2.3.96 or higher required")


def _debug(*args):
    log.debug('videotest', ' '.join(args))

# only Controller is to be shown in epydoc
__all__ = ('Controller', )


class Controller(gobject.GObject):
    """
    Controller for a video test producer, used to generate a video test feed.
    The controller's model produces a raw video test feed using videotestsrc.
    """
# FIXME: decide on a good name for prepared that says "you can do stuff with me
# now"
    gsignal('prepared')

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

        # add possible patterns
        self.view.add_pattern("SMPTE")
        self.view.add_pattern("Snow")
        self.view.add_pattern("0% Black")
        self.view.set_pattern(1)

        # add possible formats
        self.view.add_format("RGB")
        self.view.add_format("YUY2")
        self.view.add_format("I420")
        self.view.set_format(0)

        self.view.connect('width-changed', self.view_width_changed_cb)
        self.view.connect('height-changed', self.view_height_changed_cb)
        self.view.connect('framerate-changed', self.view_framerate_changed_cb)
        self.view.connect('format-changed', self.view_format_changed_cb)
        self.view.connect('pattern-changed', self.view_pattern_changed_cb)
        # the model doesn't currently have a prepare

    ### callbacks

    def view_width_changed_cb(self, view, width):
        _debug("width changed to %d" % width)
        self.model.set_width(width)

    def view_height_changed_cb(self, view, height):
        _debug("height changed to %d" % height)
        self.model.set_height(height)

    def view_framerate_changed_cb(self, view, framerate):
        _debug("framerate changed to %f" % framerate)
        self.model.set_framerate(framerate)

    def view_format_changed_cb(self, view, format):
        _debug("format changed to %f" % format)
        self.model.set_format(format)

    def view_pattern_changed_cb(self, view, index):
        _debug("pattern changed to index %d" % index)
        self.model.set_pattern(index)


class View(gobject.GObject):
    gsignal('width-changed', int)
    gsignal('height-changed', int)
    gsignal('framerate-changed', float)
    gsignal('format-changed', int)
    gsignal('pattern-changed', int)

    latency = 100 # latency for timeouts on config changes

    def __init__(self):
        """
        Construct a new videotest View.
        """
        self.__gobject_init__()
        self._gladefile = os.path.join(configure.gladedir, 'videotest.glade')
        self._glade = gtk.glade.XML(self._gladefile, "videotest-widget")
        self._widget = self._glade.get_widget("videotest-widget")
        self._width_timeout = 0
        self._height_timeout = 0
        self._framerate_timeout = 0
        self._format_timeout = 0

    def prepare(self):
        # connect callbacks
        w = self._glade.get_widget("width-button")
        w.connect("value-changed", self.width_changed_cb)
        w = self._glade.get_widget("height-button")
        w.connect("value-changed", self.height_changed_cb)
        w = self._glade.get_widget("framerate-button")
        w.connect("value-changed", self.framerate_changed_cb)
        w = self._glade.get_widget("pattern-combo")
        self._pattern_combo = w
        self._pattern_model = gtk.ListStore(str)
        w.set_model(self._pattern_model)
        w.connect("changed", self.pattern_changed_cb)
        w = self._glade.get_widget("format-combo")
        self._format_combo = w
        self._format_model = gtk.ListStore(str)
        w.set_model(self._format_model)
        w.connect("changed", self.format_changed_cb)

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

    def add_format(self, description):
        'add a format description to the format combobox'
        # FIXME: for now we don't even store enum keys, which we might want
        # to do if they're added in a different order or not always start
        # at 0
        self._format_model.append((description, ))

    def set_format(self, index):
        self._format_combo.set_active(index)

    ### timeouts

    def view_width_timeout(self, widget):
        width = widget.get_value()
        self.emit('width-changed', width)
        self._width_timeout = 0
        return gtk.FALSE

    def view_height_timeout(self, widget):
        height = widget.get_value()
        self.emit('height-changed', height)
        self._height_timeout = 0
        return gtk.FALSE

    def view_framerate_timeout(self, widget):
        framerate = widget.get_value()
        self.emit('framerate-changed', framerate)
        self._framerate_timeout = 0
        return gtk.FALSE

    def view_format_timeout(self, widget):
        format = widget.get_active()
        self.emit('format-changed', format)
        self._format_timeout = 0
        return gtk.FALSE

    ### callbacks

    def width_changed_cb(self, widget):
        if not self._width_timeout:
            id = gobject.timeout_add(View.latency,
                                     self.view_width_timeout, widget)
            self._width_timeout = id

    def height_changed_cb(self, widget):
        if not self._height_timeout:
            id = gobject.timeout_add(View.latency,
                                     self.view_height_timeout, widget)
            self._height_timeout = id

    def framerate_changed_cb(self, widget):
        if not self._framerate_timeout:
            id = gobject.timeout_add(View.latency,
                                     self.view_framerate_timeout, widget)
            self._framerate_timeout = id

    def format_changed_cb(self, widget):
        if not self._format_timeout:
            id = gobject.timeout_add(View.latency,
                                     self.view_format_timeout, widget)
            self._format_timeout = id

    def pattern_changed_cb(self, widget):
        index = widget.get_active()
        self.emit('pattern-changed', index)


class Model:

    def __init__(self):
        self._src = gst.Element('videotestsrc')
        self._src.set_property('sync', True)
        self._src.get_pad('src').connect("notify::caps", self.have_caps_cb)
        self._caps = None

    def get_element(self):
        'Gets the element we should link and put in our main bin'
        return self._src

    def get_caps(self):
        'Gets the caps that should be used as filter'
        return self._caps

    def set_width(self, width):
        if not self._caps:
            return
        self._structure['width'] = width
        _debug("set_width, caps now %s" % self._caps)
        self._relink()

    def set_height(self, height):
        if not self._caps:
            return
        self._structure['height'] = height
        _debug("set_height, caps now %s" % self._caps)
        self._relink()

    def set_framerate(self, framerate):
        if not self._caps:
            return
        self._structure['framerate'] = framerate
        _debug("set_framerate,caps now %s" % self._caps)
        self._relink()

    # FIXME: use lookup table
    # FIXME: setting 'format' fourcc's doesn't work yet

    def set_format(self, format):
        print "SET FORMAT"
        if not self._caps:
            return
        if format > 2:
            return
        if format == 0:
            # RGB
            self._structure.set_name('video/x-raw-rgb')
            del self._structure['format']
        else:
            # YUV
            self._structure.set_name('video/x-raw-yuv')
            del self._structure['blue_mask']
            del self._structure['red_mask']
            del self._structure['green_mask']
            del self._structure['depth']
            del self._structure['bpp']
            del self._structure['endianness']
            if format == 1:
                self._structure['format'] = '(fourcc)YUY2'
            #elif format == 2:
            #    self._structure['format'] = 'I420'

        print("set_format,caps now %s" % self._caps)
        self._relink()

    def set_pattern(self, pattern):
        'Sets the pattern enum on videotestsrc to the given pattern enum value'
        self._src.set_property("pattern", pattern)

    def have_caps_cb(self, pad, dunno):
        caps = pad.get_negotiated_caps()
        _debug("HAVE_CAPS: pad %s, caps %s" % (pad, caps))
        self._caps = caps
        self._structure = self._caps.get_structure(0)

    def _relink(self):
        'try a relink of our pad with our caps'
        'if no caps, or no peer, then just return'
        if not self._caps:
            print "ERROR: don't have caps"
            return
        pad = self._src.get_pad('src')
        peer = pad.get_peer()
        if peer:
            # we pause our parent so we can link and unlink
            # normally we'd have relink_filtered do that for us if it worked.
            parent = self._src.get_parent()
            parent.set_state(gst.STATE_PAUSED)
            pad.unlink(peer)
            if not pad.link_filtered(peer, self._caps):
                print "ERROR: could not link %s and %s with caps %s" % (
                    pad, peer, self._caps)
            if not parent.set_state(gst.STATE_PLAYING):
                print "ERROR: could not set parent %s to playing" % parent
        _debug("gst caps of pad now %s" % pad.get_negotiated_caps())

# register our types globally
gobject.type_register(View)
gobject.type_register(Controller)

if __name__ == '__main__':
    exposed_cb_id = -1
    width = 320
    height = 240

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

    def view_width_changed_cb(widget, value, area):
        width = value
        area.set_size_request(width, height)

    def view_height_changed_cb(widget, value, area):
        height = value
        area.set_size_request(width, height)

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
    area.set_size_request(width, height)
    # FIXME: changing the area's size request this way makes it flash a lot
    controller.view.connect('width-changed', view_width_changed_cb, area)
    controller.view.connect('height-changed', view_height_changed_cb, area)
    exposed_cb_id = area.connect('expose-event', area_exposed_cb, thread, sink)
    box.add(area)
    window.add(box)
    window.show_all()

    # embed the model in our fake toplevel model
    src = controller.model.get_element()
    prev = None
    thread.add_many(src, csp, sink)
    src.link(csp)
    csp.link(sink)

    _debug("going into gtk.main")
    gtk.main()
