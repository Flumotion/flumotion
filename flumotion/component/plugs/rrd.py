# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

import os

# FIXME: use a variable like HAS_RRDTOOL like we do in similar code
try:
    import rrdtool
except ImportError:
    rrdtool = None

from flumotion.component.plugs import base
from flumotion.common import messages, i18n, log
from flumotion.common.poller import Poller

from flumotion.common.i18n import N_
T_ = i18n.gettexter()

_DEFAULT_POLL_INTERVAL = 60 # in seconds
_DEFAULT_STEP_SIZE = 300 # in seconds

__version__ = "$Rev: 7162 $"


class ComponentRRDPlug(base.ComponentPlug):
    """Class to create or update a RRD file with statistics"""

    ### ComponentPlug methods

    def start(self, component):
        self._rrdpoller = None

        self._component = component

        if not self._hasImport():
            return

        properties = self.args['properties']
        self._clientsPath = properties['clients-connected-file']
        self._bytesPath = properties['bytes-transferred-file']
        self._stepSize = properties.get('step-size', _DEFAULT_STEP_SIZE)
        self._RRDPaths = self._getRRDPaths()
        # call to update_rrd with a poll interval
        timeout = properties.get('poll-interval', _DEFAULT_POLL_INTERVAL)
        self._rrdpoller = Poller(self._updateRRD, timeout)

    def stop(self, component):
        if self._rrdpoller:
            self._rrdpoller.stop()

    def _hasImport(self):
        """Check rrdtool availability"""
        if not rrdtool:
            m = messages.Warning(T_(N_(
                "Cannot import module '%s'.\n"), 'rrdtool'),
                                    mid='rrdtool-import-error')
            m.add(T_(N_(
                "The RRD plug for this component is disabled.")))
            self._component.addMessage(m)
            return False

        return True

    def _updateRRD(self):
        """Update data in RRD file"""
        for path in self._RRDPaths:
            value = None
            if path == self._clientsPath:
                value = self._component.getClients()
            elif path == self._bytesPath:
                value = self._component.getBytesSent()

            try:
                rrdtool.update(path, 'N:%i' % value)
                self.debug('RRD file [%s] updated with value: %r',
                    path, value)
            except rrdtool.error, e:
                # We could get an error from rrdtool on converting the
                # value to a double or from not finding the file
                self.warning('RRD error: %r',
                             log.getExceptionMessage(e))

    def _getRRDPaths(self):
        """Create the RRD file using the CACTI standard configuration
           if it doesn't exist"""
        paths = []
        rrds = (
            (self._clientsPath, 'clients', 'GAUGE'),
            (self._bytesPath, 'bytes', 'DERIVE'),
        )

        for path, name, counterType in rrds:
            if not os.path.exists(path):
                try:
                    DAY = 60 * 60 * 24
                    count = [
                        8 * DAY // self._stepSize,
                        56 * DAY // (self._stepSize * 6),
                        250 * DAY // (self._stepSize * 24),
                        3000 * DAY // (self._stepSize * 288),
                    ]

                    rrdtool.create(path,
                        '-s %d' % self._stepSize,
                        'DS:%s:%s:600:0:U' % (name, counterType),
                        'RRA:AVERAGE:0.5:1:%d' % count[0],
                        'RRA:AVERAGE:0.5:6:%d' % count[1],
                        'RRA:AVERAGE:0.5:24:%d' % count[2],
                        'RRA:AVERAGE:0.5:288:%d' % count[3],
                        'RRA:MAX:0.5:1:%d' % count[0],
                        'RRA:MAX:0.5:6:%d' % count[1],
                        'RRA:MAX:0.5:24:%d' % count[2],
                        'RRA:MAX:0.5:288:%d' % count[3])
                    paths.append(path)
                    self.info("Created RRD file: '%s'", path)
                except Exception, e:
                    self.warning("Error creating RRD file '%s': %s",
                        path, log.getExceptionMessage(e))
                    m = messages.Warning(T_(N_(
                        "Could not create RRD file '%s'.\n"), path),
                        debug=log.getExceptionMessage(e),
                        mid='rrd-create-error-%s' % path)
                    self._component.addMessage(m)
            else:
                paths.append(path)
                self.info("Using existing RRD file: '%s'", path)

        return paths
