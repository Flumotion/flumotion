# -*- Mode: Python; test-case-name: flumotion.test.test_ui_fgtk -*-
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

import gobject

from flumotion.common import testsuite

try:
    import gtk
    from flumotion.ui.fvumeter import FVUMeter
except RuntimeError:
    import os
    os._exit(0)

attr = testsuite.attr

INTERVAL = 100 # in ms


class VUTest(testsuite.TestCase):

    def testScale(self):
        w = FVUMeter()

        self.assertEquals(w.iec_scale(-80.0), 0.0)
        self.assertEquals(w.iec_scale(-70.0), 0.0)
        self.assertEquals(w.iec_scale(-60.0), 2.5)
        self.assertEquals(w.iec_scale(-50.0), 7.5)
        self.assertEquals(w.iec_scale(-40.0), 15)
        self.assertEquals(w.iec_scale(-30.0), 30)
        self.assertEquals(w.iec_scale(-20.0), 50)
        self.assertEquals(w.iec_scale(-10.0), 75)
        self.assertEquals(w.iec_scale(0.0), 100)

    def testGetSet(self):
        w = FVUMeter()
        w.set_property('peak', -50.0)
        self.assertEquals(w.get_property('peak'), -50.0)
        w.set_property('decay', -50.0)
        self.assertEquals(w.get_property('decay'), -50.0)
        w.set_property('orange-threshold', -50.0)
        self.assertEquals(w.get_property('orange-threshold'), -50.0)
        w.set_property('red-threshold', -50.0)
        self.assertEquals(w.get_property('red-threshold'), -50.0)

    @attr('slow')
    def testWidget(self):
        w = FVUMeter()
        window = gtk.Window()
        window.add(w)
        window.show_all()
        gobject.timeout_add(0 * INTERVAL, w.set_property, 'peak', -50.0)
        gobject.timeout_add(1 * INTERVAL, w.set_property, 'peak', -5.0)
        gobject.timeout_add(2 * INTERVAL, gtk.main_quit)
        gtk.main()
        # these four calls make sure the window doesn't hang around during
        # other tests
        window.hide()
        gtk.main_iteration()
        window.destroy()
        gtk.main_iteration()
