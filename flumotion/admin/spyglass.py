# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
#
# flumotion/admin/spyglass.py: MVC for spyglass
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

def debug(*args):
    flumotion.utils.log.debug('spyglass', ' '.join(args))
    
class Controller(gobject.GObject):
# FIXME: decide on a good name for prepared that says "you can do stuff with me
# now"
    __gsignals__ = {
        'prepared': (gobject.SIGNAL_RUN_FIRST, None, ())
    }
    def __init__(self):
        """
        Construct a new Spyglass M-V-C object.
        This is used for viewing a video feed.
        """
        self.__gobject_init__()
        self.view = View()
        self.model = Model()

    def prepare(self):
        'returns immediately, and will report when prepared through signal'
        self.view.connect('have-xid', self.view_have_xid_cb)
        # the view's prepare is synchronous for now
        self.view.prepare()
        # the model doesn't currently have a prepare

    #FIXME: should be registered as a callback on the view instead
    def width_changed(self, widget):
        width = widget.get_value()
        print 'width has changed to %d' % width

    def height_changed(self, widget):
        height = widget.get_value()
        print 'height has changed to %d' % height

    def view_have_xid_cb(self, view, xid):
        debug("view_have_xid_cb: have xid %d" % xid)
        self.model.set_xid(xid)
        self.emit('prepared')

class View(gobject.GObject):
    __gsignals__ = {
        'have_xid': (gobject.SIGNAL_RUN_FIRST, None, (long, ))
    }

    def __init__(self):
        """
        Construct a new Spyglass View.
        """
        self.__gobject_init__()
        self._gladefile = os.path.join(flumotion.config.uidir, 'spyglass.glade')
        self._glade = gtk.glade.XML(self._gladefile, "spyglass-widget")
        self._widget = self._glade.get_widget("spyglass-widget")

    def prepare(self):
        # connect realize callback to drawing area so we know when to get
        # the xid
        area = self._glade.get_widget("spyglass-area")
        assert(area)
        self._expose_id = area.connect("expose-event", self.exposed_cb)

    def exposed_cb(self, widget, event):
        'store our xid now that we are exposed'
        widget.disconnect(self._expose_id)
        self._xid = widget.window.xid 
        debug("exposed_cb, got xid %d" % self._xid)
        self.emit('have-xid', self._xid)

    def get_widget(self):
        return self._widget

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
        debug("setting thread to PLAYING")
        thread.set_state(gst.STATE_PLAYING)

    debug("testing")
    # create fake toplevel model
    thread = gst.Thread()

    controller = Controller()
    controller.connect("prepared", controller_prepared_cb, thread)
    controller.prepare()

    # embed the view
    window = gtk.Window()
    window.connect('destroy', gtk.main_quit)
    window.add(controller.view.get_widget())
    window.show_all()

    # embed the model
    src = gst.Element('videotestsrc')
    csp = gst.Element('ffmpegcolorspace')
    sink = controller.model.get_element()
    prev = None
    for e in (src, csp, sink):
        thread.add(e)
        if prev: prev.link(e)
        prev = e
    
    debug("going into gtk.main")
    gtk.main()
