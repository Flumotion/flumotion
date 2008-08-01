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

import gettext
import os
import webbrowser

from flumotion.common.format import formatStorage
from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.ui.linkwidget import LinkWidget

__version__ = "$Rev$"
_ = gettext.gettext


class StatisticsAdminGtkNode(BaseAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'misc',
                              'httpserver', 'httpserver.glade')

    def __init__(self, *args, **kwargs):
        BaseAdminGtkNode.__init__(self, *args, **kwargs)
        self._shown = False
        self._statistics = None
        self._stats = None
        self._labels = {}
        self._link = None

    # BaseAdminGtkNode

    def haveWidgetTree(self):
        self._labels = {}
        self._statistics = self.wtree.get_widget('main_vbox')
        self.widget = self._statistics
        for labelType in ['bytes-transferred', 'connected-clients']:
            self._registerLabel(labelType)

        self._updateLabels({
            'bytes-transferred': 0,
            'connected-clients': 0,
        })
        if self._stats:
            self.shown = True
            self._updateLabels(self._stats)
            self._statistics.show_all()

        return self._statistics

    # Public API

    def setStats(self, stats):
        """Update the state containing all information used by this
        interface
        @param stats:
        @type stats: AdminComponentUIState
        """
        # Set _stats regardless of if condition
        # Used to be a race where _stats was
        # not set if widget tree was gotten before
        # ui state
        self._stats = stats

        if not self._statistics:
            # widget tree not created yet
            return

        self._updateLabels(stats)

        if not self._shown:
            # widget tree created but not yet shown
            self._shown = True
            self._statistics.show_all()

    # Private

    def _updateLabels(self, state):
        for name in self._labels:
            text = state.get(name)
            if text is not None:
                if name == 'bytes-transferred':
                    text = formatStorage(int(text)) + _('Byte')
                self._labels[name].set_text(str(text))

        uri = state.get('stream-url')
        if uri is not None:
            if not self._link:
                self._link = self._createLinkWidget(uri)
            else:
                self._link.set_uri(uri)

    def _registerLabel(self, name):
        #widgetname = name.replace('-', '_')
        # FIXME: make object member directly
        widget = self.wtree.get_widget('label-' + name)
        if not widget:
            self.warning("FIXME: no widget %s" % name)
            return

        self._labels[name] = widget

    def _createLinkWidget(self, uri):
        link = LinkWidget(uri)
        link.set_callback(self._on_link_show_url)
        link.show_all()
        holder = self.wtree.get_widget('link-holder')
        holder.add(link)
        return link

    # Callbacks

    def _on_link_show_url(self, url):
        webbrowser.open_new(url)


class HTTPFileAdminGtk(BaseAdminGtk):

    def setup(self):
        statistics = StatisticsAdminGtkNode(self.state, self.admin,
            _("Statistics"))
        self.nodes['Statistics'] = statistics
        # FIXME: maybe make a protocol instead of overriding
        return BaseAdminGtk.setup(self)

    def uiStateChanged(self, state):
        self.nodes['Statistics'].setStats(state)

GUIClass = HTTPFileAdminGtk
