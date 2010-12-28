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
import os

# import custom glade handler
from flumotion.ui import glade
from flumotion.component.base.effectsnode import EffectAdminGtkNode

__version__ = "$Rev$"

DEINTERLACE_MODE = {
    _("Automatic detection"): "auto",
    _("Force deinterlacing"): "interlaced",
}

DEINTERLACE_METHOD = {
    _("FFmpeg Deinterlacer"): "ffmpeg",
    _("Motion Adaptive: Motion Search"): "tomsmocomp",
    _("Motion Adaptive: Advanced Detection"): "greedyh",
    _("Motion Adaptive: Simple Detection"): "greedyl",
    _("Blur: Temporal"): "linearblend",
    _("Blur: Vertical"): "vfir",
    _("Television: Full resolution"): "linear",
    _("Double lines"): "scalerbob",
    _("Weave"): "weave",
    _("Progressive: Top Field First"): "weavetff",
    _("Progressive: Bottom Field First"): "weavebff"}


class DeinterlaceAdminGtkNode(EffectAdminGtkNode):
    logCategory = 'deinterlace'
    gladeFile = os.path.join('flumotion', 'component', 'effects',
                              'deinterlace', 'deinterlace.glade')

    uiStateHandlers = None

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('deinterlace-widget')
        self._mode_combobox = \
            self.wtree.get_widget('deinterlace-mode-combobox')
        self._method_combobox = \
            self.wtree.get_widget('deinterlace-method-combobox')

        # fill comboboxes
        self._mode_combobox.prefill(DEINTERLACE_MODE.items())
        self._method_combobox.prefill(DEINTERLACE_METHOD.items())
        self._mode_combobox.select_item_by_data("auto")
        self._method_combobox.select_item_by_data("ffmpeg")

        # do the callbacks for the mode setting
        self._mode_combobox.connect('changed', self._cb_mode_set)
        # do the callback for the method setting
        self._method_combobox.connect('changed', self._cb_method_set)

    def setUIState(self, state):
        EffectAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            self.uiStateHandlers = {'deinterlace-mode': self.modeSet,
                                    'deinterlace-method': self.methodSet}
        for k, handler in self.uiStateHandlers.items():
            handler(state.get(k))

    def stateSet(self, state, key, value):
        handler = self.uiStateHandlers.get(key, None)
        if handler:
            handler(value)

    def modeSet(self, mode):
        if mode is not None:
            if mode == 'disabled':
                self._method_combobox.set_sensitive(False)
                self._mode_combobox.set_sensitive(False)
            else:
                self._mode_combobox.select_item_by_data(mode)
                self._method_combobox.set_sensitive(True)
                self._mode_combobox.set_sensitive(True)

    def methodSet(self, method):
        if method is not None:
            self._method_combobox.select_item_by_data(method)

    def setModeErrback(self, failure):
        self.warning("Failure %s setting mode: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def setMethodErrback(self, failure):
        self.warning("Failure %s setting method: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def _cb_mode_set(self, widget):
        mode = widget.get_selected_data()
        d = self.effectCallRemote("setMode", mode)
        d.addErrback(self.setModeErrback)

    def _cb_method_set(self, widget):
        method = widget.get_selected_data()
        d = self.effectCallRemote("setMethod", method)
        d.addErrback(self.setModeErrback)
