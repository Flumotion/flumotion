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

import types
import os

try:
    import rrdtool
except ImportError:
    rrdtool = None

from flumotion.component.plugs import base
from flumotion.common import common, messages, i18n
from flumotion.common.poller import Poller

from flumotion.common.i18n import N_
T_ = i18n.gettexter()

_DEFAULT_POLL_INTERVAL = 60 # in seconds

__version__ = "$Rev: 7162 $"


class ComponentRRDPlug(base.ComponentPlug):
    """Class to create or update a RRD file with statistics"""

    ### ComponentPlug methods

    def start(self, component):
        self._rrdpoller = None

        if not self._hasImport(component):
            return

        self.component = component
        properties = self.args['properties']
        self._clientsPath = properties['clients-connected-file']
        self._bytesPath = properties['bytes-transferred-file']
        self._RRDPaths = self._getRRDPaths()
        # call to update_rrd with a poll interval
        timeout = properties.get('poll-interval', _DEFAULT_POLL_INTERVAL)
        self._rrdpoller = Poller(self._updateRRD, timeout)

    def stop(self, component):
        if self._rrdpoller:
            self._rrdpoller.stop()

    def _hasImport(self, component):
        """Check rrdtool availability"""
        if not rrdtool:
            m = messages.Warning(T_(N_(
                "Cannot import module '%s'.\n"), 'rrdtool'),
                                    mid='rrdtool-import-error')
            m.add(T_(N_(
                "The RRD plug for this component is disabled.")))
            component.addMessage(m)
            return False
        return True

    def _updateRRD(self):
        """Update data in RRD file"""
        for path in self._RRDPaths:
            value = None
            if path == self._clientsPath:
                value = self.component.getClients()
            elif path == self._bytesPath:
                value = self.component.getBytesSent()

            if type(value) == types.IntType:
                rrdtool.update(path, 'N:%i' % value)
                self.debug('RRD file [%s] updated with value: %s',
                    path, value)
            else:
                self.warning('RRD file [%s] not adding non-int value %r',
                    path, value)

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
                    rrdtool.create(path,
                        '--step 300', # consolidate every 300 seconds
                        'DS:%s:%s:600:0:U' % (name, counterType),
                        'RRA:AVERAGE:0.5:1:600',   # 600 x 5 mins: 2 days
                        'RRA:AVERAGE:0.5:6:700',   # 700 x 30 mins: 2 weeks
                        'RRA:AVERAGE:0.5:24:775',  # 775 x 2 hours: 2 months
                        'RRA:AVERAGE:0.5:288:797', # 775 x 24 hours: 2 years
                        'RRA:MAX:0.5:1:600',
                        'RRA:MAX:0.5:6:700',
                        'RRA:MAX:0.5:24:775',
                        'RRA:MAX:0.5:288:797')
                    paths.append(path)
                    self.info('Created RRD file: %s' % path)
                except:
                    self.warning('Error creating RRD file: %s' % path)
            else:
                paths.append(path)
                self.info('Using existing RRD file: %s' % path)

        return paths
