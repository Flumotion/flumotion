# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

"""RRD resource poller daemon for Flumotion.

Makes periodic observations on components' UI states, recording them to
RRD files. One can then extract graphs using rrdtool graph. For example,
to show a stream bandwidth graph for the last 30 minutes with the
example configuration file, in the source tree as
conf/rrdmon/default.xml, the following command makes a graph:

  rrdtool graph --end now --start end-30min --width 400 out.png \
     DEF:ds0=/tmp/stream-bitrate.rrd:http-streamer:AVERAGE \
     AREA:ds0#0000FF:"Stream bandwidth (bytes/sec)"

It would be possible to expose these graphs via HTTP, but I don't know
how useful this might be.

See L{flumotion.admin.rrdmon.config} for information on how to configure
the RRD resource poller.
"""

import os
import random
import rrdtool
import datetime
import time

from flumotion.admin import multi
from flumotion.common import log, common
from flumotion.common import eventcalendar
from flumotion.component.base import scheduler

# register the unjellyable
from flumotion.common import componentui

componentui # pyflakes

__version__ = "$Rev$"


def sourceGetFileName(source):
    return source['rrd-file']


def sourceGetName(source):
    return source['name']


def sourceGetSampleFrequency(source):
    return source['sample-frequency']


def sourceGetDS(source):

    def makeDS():
        if source['is-gauge']:
            return 'DS:%s:GAUGE:%d:U:U' % (source['name'],
                                           2*source['sample-frequency'])
        else:
            return 'DS:%s:DERIVE:%d:0:U' % (source['name'],
                                            2*source['sample-frequency'])
    return source['rrd-ds-spec'] or makeDS()


def sourceGetRRAList(source):

    def archiveGetRRA(archive):
        return 'RRA:' + archive['rra-spec']
    return [archiveGetRRA(archive) for archive in source['archives']]


def sourceGetConnectionInfo(source):
    return source['manager']


def sourceGetComponentId(source):
    return source['component-id']


def sourceGetUIStateKey(source):
    return source['ui-state-key']


class RRDMonitor(log.Loggable):
    logName = 'rrdmon'

    def __init__(self, sources):
        self.debug('started rrd monitor')
        self.multi = multi.MultiAdminModel()
        self.scheduler = scheduler.Scheduler()
        self.ensureRRDFiles(sources)
        self.connectToManagers(sources)
        self.startScheduler(sources)

    def ensureRRDFiles(self, sources):
        for source in sources:
            rrdfile = sourceGetFileName(source)
            if not os.path.exists(rrdfile):
                try:
                    self.info('Creating RRD file %s', rrdfile)
                    rrdtool.create(rrdfile,
                                   "-s", str(sourceGetSampleFrequency(source)),
                                   sourceGetDS(source),
                                   *sourceGetRRAList(source))
                except rrdtool.error, e:
                    self.warning('Could not create RRD file %s',
                                 rrdfile)
                    self.debug('Failure reason: %s',
                               log.getExceptionMessage(e))

    def connectToManagers(self, sources):
        for source in sources:
            connectionInfo = sourceGetConnectionInfo(source)
            self.multi.addManager(connectionInfo, tenacious=True)

    def startScheduler(self, sources):
        r = random.Random()
        now = datetime.datetime.now(eventcalendar.LOCAL)

        def eventInstanceStarted(eventInstance):
            self.pollData(*eventInstance.event.content)

        def eventStopped(eventInstance):
            pass

        self.scheduler.subscribe(eventInstanceStarted, eventInstanceStopped)

        for source in sources:
            freq = sourceGetSampleFrequency(source)

            # randomly offset the polling
            offset = datetime.timedelta(seconds=r.randint(0, freq))

            data = (str(sourceGetConnectionInfo(source)),
                    sourceGetComponentId(source),
                    sourceGetUIStateKey(source),
                    sourceGetName(source),
                    sourceGetFileName(source))

            # FIXME: Event never actually allowed a timedelta as rrule,
            # so I doubt this refactoring of scheduler ever worked
            calendar = eventcalendar.Calendar()
            calendar.addEvent(now.isoformat(),
                now + offset, now + offset + datetime.timedelta(seconds=1),
                data, rrule=datetime.timedelta(seconds=freq))
            self.scheduler.setCalendar(calendar)

    def pollData(self, managerId, componentId, uiStateKey, dsName,
                 rrdFile):

        def stateListToDict(l):
            return dict([(x.get('name'), x) for x in l])

        if managerId in self.multi.admins:
            admin = self.multi.admins[managerId]

            flowName, componentName = common.parseComponentId(componentId)

            flows = stateListToDict(admin.planet.get('flows'))
            if flowName not in flows:
                self.warning('not polling %s%s:%s: no such flow %s',
                             managerId, componentId, uiStateKey,
                             flowName)
                return

            components = stateListToDict(flows[flowName].get('components'))
            if componentName not in components:
                self.warning('not polling %s%s:%s: no such component %s',
                             managerId, componentId, uiStateKey,
                             componentId)
                return

            state = components[componentName]

            def gotUIState(uiState):
                if not uiState.hasKey(uiStateKey):
                    self.warning('while polling %s%s:%s: uiState has no '
                                 'key %s', managerId, componentId,
                                 uiStateKey, uiStateKey)
                else:
                    try:
                        value = '%d:%s' % (int(time.time()),
                                           uiState.get(uiStateKey))
                        self.log("polled %s%s:%s, updating ds %s = %s",
                                 managerId, componentId, uiStateKey,
                                 dsName, value)
                        rrdtool.update(rrdFile, "-t", dsName, value)
                    except rrdtool.error, e:
                        self.warning('error updating rrd file %s for '
                                     '%s%s:%s', rrdFile, managerId,
                                     componentId, uiStateKey)
                        self.debug('error reason: %s',
                                   log.getExceptionMessage(e))

            def errback(failure):
                self.warning('not polling %s%s:%s: failed to get ui '
                             'state')
                self.debug('reason: %s', log.getFailureMessage(failure))

            d = admin.componentCallRemote(state, 'getUIState')
            d.addCallbacks(gotUIState, errback)
