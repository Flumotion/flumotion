# -*- Mode: Python; test-case-name: flumotion.test.test_component_providers -*-
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

from twisted.internet import defer

from flumotion.common import log
from flumotion.component.misc.httpserver import cachemanager
from flumotion.component.misc.httpserver import cachestats
from flumotion.component.misc.httpserver import localpath
from flumotion.component.misc.httpserver.httpcached import http_client
from flumotion.component.misc.httpserver.httpcached import http_utils
from flumotion.component.misc.httpserver.httpcached import request_manager
from flumotion.component.misc.httpserver.httpcached import resource_manager
from flumotion.component.misc.httpserver.httpcached import server_selection
from flumotion.component.misc.httpserver.httpcached import strategy_basic


LOG_CATEGORY = "filereader-httpcached"

DEFAULT_CACHE_TTL = 5*60
DEFAULT_DNS_REFRESH = 60
DEFAULT_SERVER_PORT = 80
DEFAULT_PROXY_PORT = 3128
DEFAULT_PROXY_PRIORITY = 1
DEFAULT_CONN_TIMEOUT = 5
DEFAULT_IDLE_TIMEOUT = 5


class FileReaderHTTPCachedPlug(log.Loggable):
    """
    Offers a file-like interface to streams retrieved using HTTP.
    It supports:
     - Local caching with TTL expiration, and cooperative managment.
     - Load-balanced proxies with priority level of proxies (fall-back).
     - More than one IP by proxy hostname with periodic DNS refresh.
     - Connection resuming if HTTP connection got disconnected.
    """

    logCategory = LOG_CATEGORY

    def __init__(self, args):
        props = args['properties']

        cacheDir = props.get('cache-dir')
        cacheSizeInMB = props.get('cache-size')
        if cacheSizeInMB is not None:
            cacheSize = cacheSizeInMB * 10 ** 6 # in bytes
        else:
            cacheSize = None
        cleanupEnabled = props.get('cleanup-enabled')
        cleanupHighWatermark = props.get('cleanup-high-watermark')
        cleanupLowWatermark = props.get('cleanup-low-watermark')

        self.stats = cachestats.CacheStatistics()

        self.cachemgr = cachemanager.CacheManager(self.stats,
                                             cacheDir, cacheSize,
                                             cleanupEnabled,
                                             cleanupHighWatermark,
                                             cleanupLowWatermark)

        self.serverHost = props.get('server-hostname')
        self.serverPort = props.get('server-port', DEFAULT_SERVER_PORT)
        dnsRefresh = props.get('dns-refresh', DEFAULT_DNS_REFRESH)
        proxies = props.get('proxy')
        compat_proxies = props.get('proxy-name')

        selector = server_selection.ServerSelector(dnsRefresh)

        if not (proxies or compat_proxies):
            selector.addServer(self.serverHost, self.serverPort)
        else:
            if compat_proxies:
                # Add the proxies specified by name
                for proxyname in compat_proxies:
                    if '#' in proxyname:
                        proxyname, priostr = proxyname.split('#', 1)
                        priority = int(priostr)
                    else:
                        priority = DEFAULT_PROXY_PRIORITY
                    if ':' in proxyname:
                        proxyname, portstr = proxyname.split(':', 1)
                        port = int(portstr)
                    else:
                        port = DEFAULT_PROXY_PORT
                    selector.addServer(proxyname, port, priority)


            if proxies:
                # Add the proxies specified by compound properties
                for proxyProps in proxies:
                    hostname = proxyProps.get('hostname')
                    port = proxyProps.get('port', DEFAULT_PROXY_PORT)
                    priority = proxyProps.get('priority',
                                              DEFAULT_PROXY_PRIORITY)
                    selector.addServer(hostname, port, priority)

        connTimeout = props.get('connection-timeout', DEFAULT_CONN_TIMEOUT)
        idleTimeout = props.get('idle-timeout', DEFAULT_IDLE_TIMEOUT)

        client = http_client.StreamRequester(connTimeout, idleTimeout)

        reqmgr = request_manager.RequestManager(selector, client)

        cacheTTL = props.get('cache-ttl', DEFAULT_CACHE_TTL)

        self.strategy = strategy_basic.CachingStrategy(self.cachemgr,
                                                       reqmgr, cacheTTL)

        self.resmgr = resource_manager.ResourceManager(self.strategy,
                                                       self.stats)

    def start(self):
        d = defer.Deferred()
        d.addCallback(lambda _: self.cachemgr.setUp())
        d.addCallback(lambda _: self.strategy.setup())
        d.addCallback(lambda _: self) # Don't return internal references
        d.callback(None)
        return d

    def stop(self):
        d = defer.Deferred()
        d.addCallback(lambda _: self.strategy.cleanup())
        d.addCallback(lambda _: self) # Don't return internal references
        d.callback(None)
        return d

    def open(self, path):
        url = http_utils.Url(hostname=self.serverHost,
                             port=self.serverPort,
                             path=path)
        return self.resmgr.getResourceFor(url)
