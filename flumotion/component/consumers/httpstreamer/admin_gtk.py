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
import time

from flumotion.common.mimetypes import launchApplicationByUrl
from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.ui.linkwidget import LinkWidget

_ = gettext.gettext
__version__ = "$Rev$"


class StatisticsAdminGtkNode(BaseAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'consumers',
                              'httpstreamer', 'httpstreamer.glade')

    def __init__(self, *args, **kwargs):
        BaseAdminGtkNode.__init__(self, *args, **kwargs)
        self._statistics = None
        self._shown = False
        self._stats = None
        self._link = None
        self._labels = {}

    # BaseAdminGtkNode

    def haveWidgetTree(self):
        self._labels = {}
        self._statistics = self.wtree.get_widget('main_vbox')
        self.widget = self._statistics

        for name in ['uptime', 'mime', 'current-bitrate', 'bitrate',
                     'totalbytes']:
            self._registerLabel('stream-' + name)
        for name in ['current', 'average', 'max', 'peak', 'peak-time']:
            self._registerLabel('clients-' + name)
        for name in ['bitrate', 'bitrate-current', 'totalbytes']:
            self._registerLabel('consumption-' + name)

        if self._stats:
            self._shown = True
            self._updateLabels(self._stats)
            self._statistics.show_all()

        return self._statistics

    def setStats(self, stats):
        # Set _stats regardless of if condition
        # Used to be a race where _stats was
        # not set if widget tree was gotten before
        # ui state
        self._stats = stats
        if not self._statistics:
            return

        self._updateLabels(stats)

        if not self._shown:
            # widget tree created but not yet shown
            self._shown = True
            self._statistics.show_all()

    # Private

    def _registerLabel(self, name):
        # widgetname = name.replace('-', '_')
        # FIXME: make object member directly
        widget = self.wtree.get_widget('label-' + name)
        if not widget:
            print "FIXME: no widget %s" % name
            return

        self._labels[name] = widget

    def _updateLabels(self, state):
        # changed in 0.1.9.1 to be int so we can localize time
        peakTime = state.get('clients-peak-time')
        if not isinstance(peakTime, str):
            peakTime = time.strftime("%c", time.localtime(peakTime))

        self._labels['clients-peak-time'].set_text(peakTime)

        for name in self._labels:
            if name == 'clients-peak-time':
                continue
            text = state.get(name)
            if text is None:
                text = ''

            self._labels[name].set_text(text)

        uri = state.get('stream-url', '')
        if not self._link and uri:
            self._link = self._createLinkWidget(uri)

        disable = state.get('stream-mime') is None
        tooltip = _('The stream is temporarly unavailable.\n'
                  'No data is being transmitted right now.')
        if self._link:
            self._link.set_sensitive(not disable)
            self._link.set_tooltip_text((disable and tooltip) or '')
            self._link.set_uri(uri)

    def _createLinkWidget(self, uri):
        holder = self.wtree.get_widget('link-holder')
        if holder is None:
            return
        link = LinkWidget(uri)
        link.set_callback(self._on_link_show_url)
        link.show_all()
        holder.add(link)
        return link

    # Callbacks

    def _on_link_show_url(self, url):
        launchApplicationByUrl(url, self._stats.get('stream-mime'))


class HTTPStreamerAdminGtk(BaseAdminGtk):

    def setup(self):
        statistics = StatisticsAdminGtkNode(self.state, self.admin,
            _("Statistics"))
        self.nodes['Statistics'] = statistics
        # FIXME: maybe make a protocol instead of overriding
        return BaseAdminGtk.setup(self)

    def uiStateChanged(self, state):
        self.nodes['Statistics'].setStats(state)

    # FIXME: tie this to the statistics node better

    def component_statsChanged(self, stats):
        # FIXME: decide on state/stats/statistics
        self.nodes['Statistics'].setStats(stats)

    def component_logMessage(self, message):
        self.nodes['Log'].logMessage(message)

GUIClass = HTTPStreamerAdminGtk
