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


class VideoscaleAdminGtkNode(EffectAdminGtkNode):
    logCategory = 'videoscale-admin'
    gladeFile = os.path.join('flumotion', 'component', 'effects',
                              'videoscale', 'videoscale.glade')

    uiStateHandlers = None

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('videoscale-vbox')
        self._height = self.wtree.get_widget('videoscale-height')
        self._width = self.wtree.get_widget('videoscale-width')
        self._par_n = self.wtree.get_widget('videoscale-par_n')
        self._par_d = self.wtree.get_widget('videoscale-par_d')
        self._is_square = self.wtree.get_widget('videoscale-is_square')
        self._add_borders = self.wtree.get_widget('videoscale-add_borders')
        self._apply = self.wtree.get_widget('videoscale-apply')

        # do the callbacks for the mode setting
        self._height.connect('value-changed', self._cb_height)
        self._width.connect('value-changed', self._cb_width)
        self._par_n.connect('value-changed', self._cb_par)
        self._par_d.connect('value-changed', self._cb_par)
        self._is_square.connect('toggled', self._cb_is_square)
        self._add_borders.connect('toggled', self._cb_add_borders)
        self._apply.connect('clicked', self._cb_apply)

    def setUIState(self, state):
        EffectAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            uiStateHandlers = {'videoscale-width': self.widthSet,
                               'videoscale-height': self.heightSet,
                               'videoscale-is-square': self.isSquareSet,
                               'videoscale-add-borders': self.addBordersSet}
            self.uiStateHandlers = uiStateHandlers

        for k, handler in self.uiStateHandlers.items():
            handler(state.get(k))

    def stateSet(self, state, key, value):
        handler = self.uiStateHandlers.get(key, None)
        if handler:
            handler(value)

    def addBordersSet(self, add_borders):
        if add_borders is not None:
            self._add_borders.set_active(add_borders)

    def isSquareSet(self, is_square):
        if is_square is not None:
            self._is_square.set_active(is_square)

    def widthSet(self, width):
        if width is not None:
            self._width.handler_block_by_func(self._cb_width)
            self._width.set_value(width)
            self._width.handler_unblock_by_func(self._cb_width)

    def heightSet(self, height):
        if height is not None:
            self._height.handler_block_by_func(self._cb_height)
            self._height.set_value(height)
            self._height.handler_unblock_by_func(self._cb_height)

    def _cb_height(self, widget):
        height = widget.get_value_as_int()
        d = self.effectCallRemote("setHeight", height)
        d.addErrback(self.setErrback)

    def _cb_width(self, widget):
        width = widget.get_value_as_int()
        d = self.effectCallRemote("setWidth", width)
        d.addErrback(self.setErrback)

    def _cb_par(self, _):
        par_n = self._par_n.get_value_as_int()
        par_d = self._par_d.get_value_as_int()
        d = self.effectCallRemote("setPAR", (par_n, par_d))
        d.addErrback(self.setErrback)

    def _cb_is_square(self, widget):
        is_square = self._is_square.get_active()
        d = self.effectCallRemote("setIsSquare", is_square)
        d.addErrback(self.setErrback)

    def _cb_add_borders(self, widget):
        add_borders = self._add_borders.get_active()
        d = self.effectCallRemote("setAddBorders", add_borders)
        d.addErrback(self.setErrback)

    def _cb_apply(self, widget):
        d = self.effectCallRemote("apply")
        d.addErrback(self.setErrback)

    def setErrback(self, failure):
        self.warning("Failure %s setting property: %s" % (
            failure.type, failure.getErrorMessage()))
        return None
