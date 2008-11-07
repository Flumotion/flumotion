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

import time
import gettext
import os
import webbrowser

from flumotion.common.i18n import N_
from flumotion.common.format import formatTime, formatStorage, formatTimeStamp
from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.ui.linkwidget import LinkWidget

__version__ = "$Rev$"
_ = gettext.gettext


class StatisticsAdminGtkNode(BaseAdminGtkNode):

    def __init__(self, *args, **kwargs):
        BaseAdminGtkNode.__init__(self, *args, **kwargs)
        self._shown = False
        self._state = None
        self._reqStats = {} # {name: (widget, converter, format, default)}

    # BaseAdminGtkNode

    def haveWidgetTree(self):
        self._reqStats = {}
        self.widget = self._initWidgets(self.wtree)
        if self._state:
            self._shown = True
            self._refreshStats(self._state)
            self.widget.show()
        else:
            self._defaultStats()
        return self.widget

    # Public API

    def setStats(self, state):
        """Update the state containing all information used by this
        interface
        @param state:
        @type state: AdminComponentUIState
        """
        # Set _stats regardless of if condition
        # Used to be a race where _stats was
        # not set if widget tree was gotten before
        # ui state
        self._state = state

        if not self.widget:
            # widget tree not created yet
            return

        # Update the statistics
        self._refreshStats(state)

        self._onStateSet(state)

        if not self._shown:
            # widget tree created but not yet shown
            self._shown = True
            self.widget.show_all()

    # Protected

    def _initWidgets(self, wtree):
        raise NotImplementedError

    def _onStateSet(self, state):
        pass

    def _defaultStats(self):
        pass

    def _refreshStats(self, state):
        pass

    # Private

    def _regReqStat(self, name, converter=str, format="%s", default=0):
        widget = self.wtree.get_widget('label-' + name)
        if not widget:
            self.warning("FIXME: no widget %s" % name)
            return
        self._reqStats[name] = (widget, converter, format, default)

    def _refreshStatistics(self, state):
        for name in self._reqStats:
            widget, converter, format, default = self._reqStats[name]
            value = state.get(name)
            if value is not None:
                widget.set_text(format % converter(value))
            else:
                widget.set_text(format % converter(default))

    def _updateStatistic(self, name, value):
        if name not in self._reqStats:
            return
        widget, converter, format, default = self._reqStats[name]
        if value is not None:
            widget.set_text(format % converter(value))
        else:
            widget.set_text(format % converter(default))


class ServerStatsAdminGtkNode(StatisticsAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'misc',
                             'httpserver', 'httpserver.glade')

    def __init__(self, *args, **kwargs):
        StatisticsAdminGtkNode.__init__(self, *args, **kwargs)
        self._uptime = None
        self._link = None

    # StatisticsAdminGtkNode

    def _initWidgets(self, wtree):
        statistics = wtree.get_widget('main_vbox')
        self._uptime = wtree.get_widget('label-server-uptime')
        self._regReqStat('current-request-count', _formatClientCount)
        self._regReqStat('mean-request-count', _formatClientCount)
        self._regReqStat('request-count-peak', _formatClientCount)
        self._regReqStat('request-count-peak-time', _formatTimeStamp,
                         _("at %s"))
        self._regReqStat('current-request-rate', _formatReqRate)
        self._regReqStat('mean-request-rate', _formatReqRate)
        self._regReqStat('request-rate-peak', _formatReqRate)
        self._regReqStat('request-rate-peak-time', _formatTimeStamp,
                         _("at %s"))
        self._regReqStat('total-bytes-sent', _formatBytes)
        self._regReqStat('current-bitrate', _formatBitrate)
        self._regReqStat('mean-bitrate', _formatBitrate)
        self._regReqStat('bitrate-peak', _formatBitrate)
        self._regReqStat('bitrate-peak-time', _formatTimeStamp, _("at %s"))
        self._regReqStat('mean-file-read-ratio', _formatPercent)
        return statistics

    # BaseAdminGtkNode

    def stateSetitem(self, state, key, subkey, value):
        if key == "request-statistics":
            self._updateStatistic(subkey, value)

    # StatisticsAdminGtkNode

    def _refreshStats(self, state):
        self._refreshStatistics(state.get("request-statistics", {}))

    def _defaultStats(self):
        self._refreshStatistics({})

    def _onStateSet(self, state):
        # Update the URI
        uri = state.get('stream-url')
        if uri is not None:
            if not self._link:
                self._link = self._createLinkWidget(uri)
            else:
                self._link.set_uri(uri)

        # Update Server Uptime
        uptime = state.get('server-uptime')
        self._uptime.set_text(formatTime(uptime))

    # Private

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


class CacheStatsAdminGtkNode(StatisticsAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'misc',
                             'httpserver', 'httpserver.glade')

    def show(self):
        if self.widget:
            self.widget.show()

    def hide(self):
        if self.widget:
            self.widget.hide()

    # StatisticsAdminGtkNode

    def _initWidgets(self, wtree):
        statistics = wtree.get_widget('cache_vbox')
        self._regReqStat('cache-usage-estimation', _formatBytes)
        self._regReqStat('cache-usage-ratio-estimation', _formatPercent)
        self._regReqStat('cache-hit-count')
        self._regReqStat('temp-hit-count')
        self._regReqStat('cache-miss-count')
        self._regReqStat('cache-outdate-count')
        self._regReqStat('cache-read-ratio', _formatPercent)
        self._regReqStat('cleanup-count')
        self._regReqStat('last-cleanup-time', _formatTimeStamp)
        self._regReqStat('current-copy-count')
        self._regReqStat('finished-copy-count')
        self._regReqStat('cancelled-copy-count')
        return statistics


    # BaseAdminGtkNode

    def stateSetitem(self, state, key, subkey, value):
        if key == "provider-statistics":
            self._updateStatistic(subkey, value)

    # StatisticsAdminGtkNode

    def _refreshStats(self, state):
        self._refreshStatistics(state.get("provider-statistics", {}))

    def _defaultStats(self):
        self._refreshStatistics({})


def _formatClientCount(value):
    if isinstance(value, (int, long)):
        format = gettext.ngettext(N_("%d client"), N_("%d clients"), value)
    else:
        format = gettext.ngettext(N_("%.2f client"), N_("%.2f clients"), value)
    return format % value


def _formatTimeStamp(value):
    return time.strftime("%c", time.localtime(value))


def _formatReqRate(value):
    return _("%.2f requests/m") % float(value * 60)


def _formatBytes(value):
    return formatStorage(value) + _('Byte')


def _formatBitrate(value):
    return formatStorage(value) + _('bit/s')


def _formatPercent(value):
    return "%.2f %%" % (value * 100.0)


class HTTPFileAdminGtk(BaseAdminGtk):

    def setup(self):
        statistics = ServerStatsAdminGtkNode(self.state, self.admin,
                                             _("Statistics"))
        self.nodes['Statistics'] = statistics
        #FIXME: We need to figure out how to create or delete
        #       a nodes after receiving the UI State,
        #       so we do not have a cache tab when not using a caching plug.
        #cache = CacheStatsAdminGtkNode(self.state, self.admin, _("Cache"))
        #self.nodes["Cache"] = cache
        # FIXME: maybe make a protocol instead of overriding
        return BaseAdminGtk.setup(self)

    def uiStateChanged(self, state):
        self.nodes['Statistics'].setStats(state)
        #FIXME: Same as for the setup method.
        #if state:
        #    providerName = None
        #    providerStats = state.get("provider-statistics")
        #    if providerStats:
        #        providerName = providerStats.get("provider-name")
        #    if providerName and providerName.startswith("cached-"):
        #        self.nodes['Cache'].setStats(state)
        #        self.nodes["Cache"].show()
        #    else:
        #        self.nodes["Cache"].hide()


GUIClass = HTTPFileAdminGtk
