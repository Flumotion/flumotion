# -*- Mode: Python; test-case-name: flumotion.test.test_component_providers -*-
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


import operator
import random
import socket

from twisted.internet import base, defer, threads, reactor
from twisted.python import threadpool
from flumotion.common import log

DEFAULT_PRIORITY = 1.0
DEFAULT_REFRESH_TIMEOUT = 300

LOG_CATEGORY = "server-selector"


class ThreadedResolver(base.ThreadedResolver):

    def __init__(self, reactor, sk=socket):
        base.ThreadedResolver.__init__(self, reactor)
        self.socket = sk

    def getHostByNameEx(self, name, timeout = (1, 3, 11, 45)):
        if timeout:
            timeoutDelay = reduce(operator.add, timeout)
        else:
            timeoutDelay = 60
        userDeferred = defer.Deferred()
#        lookupDeferred = threads.deferToThreadPool(
#            self.reactor, self.reactor.getThreadPool(),
        lookupDeferred = threads.deferToThread(
            self.socket.gethostbyname_ex, name)
        cancelCall = self.reactor.callLater(
            timeoutDelay, self._cleanup, name, lookupDeferred)
        self._runningQueries[lookupDeferred] = (userDeferred, cancelCall)
        lookupDeferred.addBoth(self._checkTimeout, name, lookupDeferred)
        return userDeferred


class ServerSelector(log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, timeout=DEFAULT_REFRESH_TIMEOUT, sk=socket):
        self.servers = {}
        self.hostnames = {}
        self.timeout = timeout
        self.socket = socket

        self._resolver = ThreadedResolver(reactor, sk)
        self._refresh = None

    def _addCallback(self, h, hostname, port, priority):
        ip_list = h[2]
        for ip in ip_list:
            s = Server(ip, port, priority)
            if s not in self.servers[priority]:
                self.servers[priority].append(s)

        self.hostnames[hostname] = (ip_list, priority, port)

    def _addErrback(self, err):
        self.warning("Could not resolve host %s",
                     log.getFailureMessage(err))
        return

    def addServer(self, hostname, port, priority=DEFAULT_PRIORITY):
        """
        Add a hostname to the list of servers, with a priority. (in
        increasing order, 1 comes before 2).

        @return None
        """
        self.hostnames[hostname] = ([], priority, port)
        if priority not in self.servers:
            self.servers[priority] = []

        d = self._resolver.getHostByNameEx(hostname)
        d.addCallbacks(self._addCallback,
                       self._addErrback,
                       callbackArgs=(hostname, port, priority))
        return d

    def getServers(self):
        """
        Order the looked up servers by priority, and return them.

        @return a generator of Server
        """
        priorities = self.servers.keys()
        priorities.sort()
        for p in priorities:
            servers = self.servers[p]
            random.shuffle(servers)
            for s in servers:
                yield s

    def _refreshCallback(self, host, hostname):
        # FIXME: improve me, avoid data duplication, Server info loss..
        new_ips = host[2]
        old_ips, priority, port = self.hostnames[hostname]
        to_be_added = [ip for ip in new_ips if ip not in old_ips]
        to_be_removed = [ip for ip in old_ips if ip not in new_ips]
        servers = self.servers[priority]
        for ip in to_be_added:
            servers.append(Server(ip, port, priority))
            self.hostnames[hostname][0].append(ip)
        for ip in to_be_removed:
            for s in servers:
                if s.ip == ip:
                    servers.remove(s)
                    self.hostnames[hostname][0].remove(ip)
        self.servers[priority] = servers

    def refreshServers(self):
        dl = []
        for h in self.hostnames.keys():
            d = self._resolver.getHostByNameEx(h)
            d.addCallbacks(self._refreshCallback, self._addErrback,
                           callbackArgs=(h, ))
            dl.append(d)
        self._resetRefresh()
        d = defer.DeferredList(dl)
        d.addCallback(lambda _: self)
        return d

    def _resetRefresh(self):
        if self.timeout:
            self._refresh = reactor.callLater(self.timeout, self._onRefresh)

    def _onRefresh(self):
        self.refreshServers()

    def setup(self):
        return self.refreshServers()

    def cleanup(self):
        if self._refresh:
            self._refresh.cancel()
        self._refresh = None


class Server(object):

    def __init__(self, ip, port, priority):
        self.ip = ip
        self.port = port
        self.priority = priority

    def reportError(self, code):
        pass

    def __repr__(self):
        return "<%s: %s:%d>" % (type(self).__name__, self.ip, self.port)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__
