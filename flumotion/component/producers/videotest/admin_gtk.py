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

from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode

class PatternNode(BaseAdminGtkNode):
    def render(self):
        # FIXME: gladify
        self.widget = gtk.Table(1, 2)
        label = gtk.Label("Pattern:")
        self.widget.attach(label, 0, 1, 0, 1, 0, 0, 6, 6)
        label.show()
        d = self.callRemote("getElementProperty", "source", "pattern")
        d.addCallback(self.getPatternCallback)
        d.addErrback(self.getPatternErrback)
        d.addCallback(lambda result: self.widget)
        return d

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
        self.pattern_changed_id = self.combobox_pattern.connect('changed',
            self.cb_pattern_changed)
        self.widget.attach(self.combobox_pattern, 1, 2, 0, 1, 0, 0, 6, 6)
        self.combobox_pattern.show()

    def getPatternErrback(self, failure):
        # FIXME: this should throw up a nice error dialog with debug info
        self.warning("Failure %s getting pattern: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def cb_pattern_changed(self, combobox):
        def _setPatternErrback(failure):
            self.warning("Failure %s getting pattern: %s" % (
                failure.type, failure.getErrorMessage()))
            return None

        pattern = combobox.get_value()
        d = self.callRemote("setElementProperty", "source", "pattern", pattern)
        d.addErrback(_setPatternErrback)

    def propertyChanged(self, name, value):
        if name == "pattern":
            self.debug("pattern changed to %r" % value)
            c = self.combobox_pattern
            id = self.pattern_changed_id
            c.handler_block(id)
            c.set_active(value)
            c.handler_unblock(id)

class VideoTestAdminGtk(BaseAdminGtk):
    def setup(self):
        # FIXME: have constructor take self instead ?
        pattern = PatternNode(self.name, self.admin, self.view)
        self._nodes = {'Pattern': pattern}

    # FIXME: move to base class, make _nodes a public member
    def getNodes(self):
        return self._nodes

    def component_propertyChanged(self, name, value):
        # FIXME: tie to correct node better
        self._nodes['Pattern'].propertyChanged(name, value)

GUIClass = VideoTestAdminGtk
