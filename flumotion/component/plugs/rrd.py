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

from flumotion.component.plugs import base
from flumotion.common import common, messages
from flumotion.common.poller import Poller
import types
import os

try:
    import rrdtool
except ImportError:
    rrdtool = False

POLL_INTERVAL = 60 # in seconds


class ComponentRRDPlug(base.ComponentPlug):
    """Class to create or update a RRD file with statistics"""

    def start(self, component):
        """start values to update and/or create a RRD file"""
        self._rrdpoller = None
        self.ready = []

        if not self._check_import(component):
            return

        self.component = component
        properties = self.args['properties']
        self.timeout = properties.get('poll-interval', POLL_INTERVAL)
        self.clients = properties['clients-connected-file']
        self.bytes = properties['bytes-transferred-file']
        self.ready = self.check_rrd()
        self.lastbytes = 0
        # call to update_rrd with a config timeout
        self._rrdpoller = Poller(self.update_rrd, self.timeout)

    def _check_import(self, component):
        """Check rrdtool availability"""
        if not rrdtool:
            mesg = messages.Warning("rrdtool module is not present "
                                    "in your system. This plug [rrd] "
                                    "is disabled now.",
                                    id='rrdtool-import-error')
            component.addMessage(mesg)
            return False
        return True

    def stop(self, component):
        """Stop the poller"""
        if self._rrdpoller:
            self._rrdpoller.stop()

    def update_rrd(self):
        """Update data in RRD file"""
        for item in self.ready:
            value = None
            if item == self.clients:
                value = self.component.getClients()
            elif item == self.bytes:
                value = self.component.getBytesSent()
            if type(value) == types.IntType:
                rrdtool.update(item, 'N:%i'%value)
                self.info('RRD file [%s] updated with value: %s'%
                    (item, value))

    def check_rrd(self):
        """Create the RRD file using the CACTI standard configuration
           if it doesn't exist"""
        rrdready = []
        rrds = ((self.clients, 'GAUGE'),
                (self.bytes, 'DERIVE'))
        for file, rrdtype in rrds:
            if not os.path.exists(file):
                try:
                    rrdtool.create(file,
                        '-s 300',
                        'DS:snmp_oid:%s:600:0:1000000000' % rrdtype,
                        'RRA:AVERAGE:0.5:1:600',
                        'RRA:AVERAGE:0.5:6:700',
                        'RRA:AVERAGE:0.5:24:775',
                        'RRA:AVERAGE:0.5:288:797',
                        'RRA:MAX:0.5:1:600',
                        'RRA:MAX:0.5:6:700',
                        'RRA:MAX:0.5:24:775',
                        'RRA:MAX:0.5:288:797')
                    rrdready.append(file)
                    self.info('RRD file created: %s' % file)
                except:
                    self.info('Error creating RRD file: %s' % file)
            else:
                rrdready.append(file)
                self.info('Using RRD file: %s' % file)
        return rrdready
