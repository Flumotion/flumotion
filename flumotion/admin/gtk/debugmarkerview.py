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

"""dialog to display debug markers"""

import gettext

import gobject

from flumotion.common.pygobject import gsignal
from flumotion.extern.log import log
from flumotion.ui.glade import GladeWindow

__version__ = "$Rev: 6581 $"
_ = gettext.gettext


class DebugMarkerDialog(GladeWindow):
    gladeFile = 'debug-marker.glade'

    gsignal('set-marker', str, int)

    def __init__(self):
        debugLevels = log.getLevelNames()
        GladeWindow.__init__(self)
        pos = 0
        self._debugLevelCode = {}
        for level in debugLevels:
            if level == 'ERROR':
                continue
            self.level_selection.get_model().insert(pos, [level])
            self._debugLevelCode[pos] = log.getLevelInt(level)
            pos = pos+1

    def _updateOkButtonSensitiveness(self):
        if (self.marker_entry.get_text() and
            self.level_selection.get_active()!=-1):
            self.ok_button.set_sensitive(True)
        else:
            self.ok_button.set_sensitive(False)

    def _emitMarker(self):
        level = self._debugLevelCode[self.level_selection.get_active()]
        self.emit('set-marker', self.marker_entry.get_text(), level)

    # Callbacks

    def on_ok_button_clicked_cb(self, button):
        self._emitMarker()
        self.destroy()

    def on_cancel_button_clicked_cb(self, button):
        self.destroy()

    def on_marker_entry_changed_cb(self, entry):
        self._updateOkButtonSensitiveness()

    def on_level_selection_changed_cb(self, combo):
        self._updateOkButtonSensitiveness()

gobject.type_register(DebugMarkerDialog)
