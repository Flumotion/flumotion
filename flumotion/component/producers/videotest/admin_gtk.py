# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

from gettext import gettext as _

import gtk
from flumotion.common import enum
from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.ui import fgtk

__version__ = "$Rev$"


VideoTestPattern = enum.EnumClass(
    'VideoTestPattern',
    ['Bars', 'Snow', 'Black', 'White', 'Red', 'Green', 'Blue', 'Checkers-1',
            'Checkers-2', 'Checkers-4', 'Checkers-8', 'Circular', 'Blink',
            'Bars 75%', 'Zone-plate'],
    [_('SMPTE 100% color bars'),
     _('Random (television snow)'),
     _('100% Black'),
     _('100% White'),
     _('100% Red'),
     _('100% Green'),
     _('100% Blue'),
     _('Checkers 1px'),
     _('Checkers 2px'),
     _('Checkers 4px'),
     _('Checkers 8px'),
     _('Circular'),
     _('Blink'),
     _('SMPTE 75% color bars'),
     _('Zone plate')])


class PatternNode(BaseAdminGtkNode):
    uiStateHandlers = None

    def render(self):
        # FIXME: gladify
        self.widget = gtk.Table(1, 2)
        label = gtk.Label(_("Pattern:"))
        self.widget.attach(label, 0, 1, 0, 1, 0, 0, 6, 6)
        label.show()
        self.combobox_pattern = fgtk.FProxyComboBox()
        self.combobox_pattern.set_enum(VideoTestPattern)
        self.pattern_changed_id = self.combobox_pattern.connect('changed',
            self.cb_pattern_changed)
        self.widget.attach(self.combobox_pattern, 1, 2, 0, 1, 0, 0, 6, 6)
        self.combobox_pattern.show()
        return BaseAdminGtkNode.render(self)

    def setUIState(self, state):
        BaseAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            self.uiStateHandlers = {'pattern': self.patternSet}
        for k, handler in self.uiStateHandlers.items():
            handler(state.get(k))

    def cb_pattern_changed(self, combobox):

        def _setPatternErrback(failure):
            self.warning("Failure %s setting pattern: %s" % (
                failure.type, failure.getErrorMessage()))
            return None

        pattern = combobox.get_active()
        d = self.callRemote("setPattern", pattern)
        d.addErrback(_setPatternErrback)

    def patternSet(self, value):
        self.debug("pattern changed to %r" % value)
        c = self.combobox_pattern
        hid = self.pattern_changed_id
        c.handler_block(hid)
        c.set_active(value)
        c.handler_unblock(hid)

    def stateSet(self, state, key, value):
        handler = self.uiStateHandlers.get(key, None)
        if handler:
            handler(value)


class VideoTestAdminGtk(BaseAdminGtk):

    def setup(self):
        # FIXME: have constructor take self instead ?
        pattern = PatternNode(self.state, self.admin, title=_("Pattern"))
        self.nodes['Pattern'] = pattern
        return BaseAdminGtk.setup(self)

GUIClass = VideoTestAdminGtk
