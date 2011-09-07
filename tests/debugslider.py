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
# Author: Andy Wingo <wingo@pobox.com>
#
# Headers in this file shall remain intact.

import gtk
from gtk import gdk
import gobject

#import pygst
#pygst.require('0.10')
import gst


class DebugSlider(gtk.HScale):

    def __init__(self):
        adj = gtk.Adjustment(int(gst.debug_get_default_threshold()),
                             0, 5, 1, 0, 0)
        gtk.HScale.__init__(self, adj)
        self.set_digits(0)
        self.set_draw_value(True)
        self.set_value_pos(gtk.POS_TOP)

        def value_changed(self):
            newlevel = int(self.get_adjustment().get_value())
            gst.debug_set_default_threshold(newlevel)

        self.connect('value-changed', value_changed)

if __name__ == '__main__':
    p = gst.parse_launch('fakesrc ! fakesink')
    p.set_state(gst.STATE_PLAYING)

    w = gtk.Window()
    s = DebugSlider()
    w.add(s)
    s.show()
    w.set_default_size(200, 40)
    w.show()
    w.connect('delete-event', lambda *args: gtk.main_quit())
    gtk.main()
