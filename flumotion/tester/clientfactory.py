# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
#
# flumotion/tester/clientfactory.py: test client factory
#
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import time
import gobject

from flumotion.tester import httpclient
from flumotion.utils import log

from flumotion.tester import client

class ClientFactory(log.Loggable):

    logCategory = "clientfactory"

    def __init__(self, loop, url, maxclients):
        self.count = 0
        self.clients = {}
        self.loop = loop
        self.maxclients = maxclients
        self.url = url
        self.results = {}
        for i in range(client.STOPPED_SUCCESS, client.STOPPED_LAST + 1):
            self.results[i] = 0

    def _client_stopped_cb(self, client, id, result):
        self.info("%4d: stopped: %d" % (id, result))
        if self.results.has_key(result):
            self.results[result] += 1
        else:
            self.results[result] = 1
        del self.clients[id]
        self.info("####: %d clients" % len(self.clients))

    def run(self):
        self.log("run() start")
        self.count = self.count + 1
        if self.count > self.maxclients:
            if len(self.clients) > 0:
                self.info("WAIT: %d clients" % len(self.clients))
                #print "WAIT: clients %s" % self.clients.keys()
                time.sleep(1)
                return True
            self.info("All clients gone, done.")
            self.loop.quit()
            return False
        self.info("%4d: creating." % self.count)
        client = httpclient.HTTPClientStatic(self.count, self.url, 5.0, 51300 + self.count)
        client.connect('stopped', self._client_stopped_cb)
        client.set_stop_size(50000)
        self.clients[self.count] = client
        gobject.idle_add(client.open)
        self.info("%4d: created." % self.count)
        self.info("####: %d clients" % len(self.clients))
        self.log("run() finish")
        return True

    def stats(self):
        'print some stats at the end of the run'
        print "successful    clients: %d" % self.results[client.STOPPED_SUCCESS]
        print "refused       clients: %d" % self.results[client.STOPPED_REFUSED]
        print "error         clients: %d" % self.results[client.STOPPED_ERROR]
        print "connect error clients: %d" % self.results[client.STOPPED_CONNECT_ERROR]
        print "read error    clients: %d" % self.results[client.STOPPED_READ_ERROR]
