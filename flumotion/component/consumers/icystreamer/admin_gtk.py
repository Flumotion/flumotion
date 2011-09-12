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

import os
import gettext

from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.component.common.streamer.admin_gtk import StreamerAdminGtk

_ = gettext.gettext
__version__ = "$Rev$"


class IcyAdminGtkNode(BaseAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'consumers',
                              'icystreamer', 'icytab.glade')

    def __init__(self, *args, **kwargs):
        BaseAdminGtkNode.__init__(self, *args, **kwargs)
        self._icytab = None
        self._shown = False
        self._stats = None
        self._labels = {}

    def haveWidgetTree(self):
        self._labels = {}
        self._icytab = self.wtree.get_widget('main_vbox')
        self.widget = self._icytab

        for name in ['title', 'timestamp']:
            self._registerLabel('icy-' + name)

        return self.widget

    def _registerLabel(self, name):
        widget = self.wtree.get_widget('label-' + name)
        if not widget:
            print "FIXME: no widget %s" % name
            return

        self._labels[name] = widget

    def _updateLabels(self, stats):
        for name in self._labels:
            text = stats.get(name, '')
            self._labels[name].set_text(text)

    def setStats(self, stats):
        # Set _stats regardless of if condition
        # Used to be a race where _stats was
        # not set if widget tree was gotten before
        # ui state
        self._stats = stats
        if not self._icytab:
            return

        self._updateLabels(stats)

        if not self._shown:
            # widget tree created but not yet shown
            self._shown = True
            self._icytab.show_all()


class ICYStreamerAdminGtk(StreamerAdminGtk):

    def setup(self):
        icytab = IcyAdminGtkNode(self.state, self.admin,
            _("ICY"))
        self.nodes['ICY'] = icytab

        StreamerAdminGtk.setup(self)

    def uiStateChanged(self, state):
        StreamerAdminGtk.uiStateChanged(self, state)

        self.nodes['ICY'].setStats(state)

GUIClass = ICYStreamerAdminGtk
