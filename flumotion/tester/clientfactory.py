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

import time
import random

import gobject

from flumotion.tester import httpclient
from flumotion.common import log

from flumotion.tester import client

__version__ = "$Rev$"


class ClientFactory(log.Loggable):

    logCategory = "clientfactory"

    """
    @type options: dict
    @param options: dictionary of optparse options
    """

    def __init__(self, loop, options):
        self.count = 0
        self.clients = {}
        self.loop = loop
        self._options = options
        self.clientcount = options.clients
        self.url = options.url
        self.results = {}
        for i in range(client.STOPPED_SUCCESS, client.STOPPED_LAST + 1):
            self.results[i] = 0
        self.info("Creating client factory for %d clients on %s" % (
            self.clientcount, self.url))
        self._rand = random.Random()

    def _client_stopped_cb(self, client, id, result):
        self.info("%4d: stopped: %d" % (id, result))
        if result in self.results:
            self.results[result] += 1
        else:
            self.results[result] = 1
        del self.clients[id]
        self.info("####: %d clients" % len(self.clients))

    def run(self):
        self.log("run() start")
        self.count = self.count + 1
        if self.count > self.clientcount:
            if len(self.clients) > 0:
                self.info("WAIT: %d clients" % len(self.clients))
                #print "WAIT: clients %s" % self.clients.keys()
                time.sleep(.1)
                return True
            self.info("All clients gone, done.")
            self.loop.quit()
            return False

        self._create_client()
        return True

    def _parse_from_range(self, string):
        value = 0
        if string.find("-") > -1:
            (min, max) = string.split("-", 2)
            value = self._rand.randint(int(min), int(max))
        else:
            value = int(string)
        return value

    # create a new client

    def _create_client(self):
        # parse readsize and readrate options
        if not self._options.readsize:
            self._options.readsize = "4096"
        size = self._parse_from_range(self._options.readsize)

        if not self._options.readrate:
            self._options.readrate = "4096"
        rate = self._parse_from_range(self._options.readrate)

        if not self._options.bytes:
            self._options.bytes = "16384"
        bytes = self._parse_from_range(self._options.bytes)

        self.info("%4d: creating, rate %d, readsize %d." %
            (self.count, rate, size))
        client = httpclient.HTTPClientStatic(self.count, self.url, rate, size)
        client.connect('stopped', self._client_stopped_cb)
        client.set_stop_size(bytes)
        self.clients[self.count] = client
        gobject.idle_add(client.open)
        self.info("%4d: created." % self.count)
        self.info("####: %d clients" % len(self.clients))
        self.log("run() finish")
        return True

    def stats(self):
        'print some stats at the end of the run'
        print "successful     clients: %d" % (
            self.results[client.STOPPED_SUCCESS], )
        print "refused        clients: %d" % (
            self.results[client.STOPPED_REFUSED], )
        print "error          clients: %d" % (
            self.results[client.STOPPED_ERROR], )
        print "connect error  clients: %d" % (
            self.results[client.STOPPED_CONNECT_ERROR], )
        print "read error     clients: %d" % (
            self.results[client.STOPPED_READ_ERROR], )
        print "internal error clients: %d" % (
            self.results[client.STOPPED_INTERNAL_ERROR], )
