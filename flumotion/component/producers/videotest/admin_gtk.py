# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/videotest/admin_gtk.py
# admin client-side code for videotest
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

import gtk

from flumotion.common import errors

#import flumotion.component
from flumotion.component.base import admin_gtk

class VideoTestAdminGtk(admin_gtk.BaseAdminGtk):
    # FIXME: do something with this
    def setUIState(self, state):
        self.updateLabels(state)
        if not self.shown:
            self.shown = True
            self.statistics.show_all()
        
    def render(self):
        # FIXME: gladify
        self.widget = gtk.Table(1, 2)
        label = gtk.Label("Pattern:")
        self.widget.attach(label, 0, 1, 0, 1, 0, 0, 6, 6)
        label.show()
        d = self.getElementProperty("source", "pattern")
        d.addCallback(self.getPatternCallback)
        
        #self.shown = False

        return self.widget

    def getPatternCallback(self, result):
        # FIXME: these need to be done there because only this piece of
        # code gets executed, so imports higher up are not present here.
        # find a better way for this.
        from flumotion.ui import fgtk
        from flumotion.wizard import enums
        self.debug("got pattern %r" % result)
        self.combobox_pattern = fgtk.FComboBox()
        self.combobox_pattern.set_enum(enums.VideoTestPattern)
        self.combobox_pattern.set_active(result)
        self.combobox_pattern.connect('changed', self.cb_pattern_changed)
        self.widget.attach(self.combobox_pattern, 1, 2, 0, 1, 0, 0, 6, 6)
        self.combobox_pattern.show()

    def cb_pattern_changed(self, combobox):
        pattern = combobox.get_value()
        d = self.setElementProperty("source", "pattern", pattern)
        # FIXME: insensitivize until we get the deferred result

GUIClass = VideoTestAdminGtk
