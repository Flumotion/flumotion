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


from flumotion.common import log
from flumotion.component.misc.httpserver.httpcached import common
from flumotion.component.misc.httpserver.httpcached import http_utils
from flumotion.component.misc.httpserver.httpcached import server_selection


LOG_CATEGORY = "request-manager"


class RequestManager(log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, selector, client):
        """
        Selector: a ServerSelector
        Client: HttpClient (StreamRequester)
        """
        self.selector = selector
        self.client = client

    def retrieve(self, consumer, url,
                 ifModifiedSince=None, ifUnmodifiedSince=None,
                 start=None, size=None):
        """
        Consumer: a StreamConsumer
        Url:
        Start: Position from which to start the download
        Size: Number of bytes to download
        IfModifiedSince:
        IfUnmodifiedSince:
        """
        servers = self.selector.getServers()
        consumer_manager = ConsumerManager(consumer, url, start, size,
                                           ifModifiedSince, ifUnmodifiedSince,
                                           servers, self.client)
        return consumer_manager.retrieve()

    def setup(self):
        return self.selector.setup()

    def cleanup(self):
        return self.selector.cleanup()


class ConsumerManager(common.StreamConsumer, log.Loggable):

    logCategory = LOG_CATEGORY

    def __init__(self, consumer, url, start, size, ifModifiedSince,
                 ifUnmodifiedSince, servers, client):
        self.consumer = consumer
        self.url = url
        self.start = start
        self.size = size
        self.ifModifiedSince = ifModifiedSince
        self.ifUnmodifiedSince = ifUnmodifiedSince
        self.servers = servers
        self.client = client
        self.current_server = None
        self.current_request = None
        self.last_error = None
        self.last_message = None

        self.logName = common.log_id(self) # To be able to track the instance

    def retrieve(self):
        try:
            s = self.servers.next()
            self.current_server = s
            if self.size is None or self.start is None:
                self.debug("Retrieving %s from %s:%s", self.url,
                           self.current_server.ip, self.current_server.port)
            else:
                self.debug("Retrieving range %s-%s (%s B) of %s from %s:%s",
                           self.start, self.start + self.size, self.size,
                           self.url, self.current_server.ip,
                           self.current_server.port)
            proxy_address = s.ip
            proxy_port = s.port
            self.current_request =\
                self.client.retrieve(self, self.url,
                                     proxyAddress=proxy_address,
                                     proxyPort=proxy_port,
                                     ifModifiedSince=self.ifModifiedSince,
                                     ifUnmodifiedSince=self.ifUnmodifiedSince,
                                     start=self.start, size=self.size)
            self.log("Retrieving data using %s", self.current_request.logName)
            return self
        except StopIteration:
            code = self.last_error or common.SERVER_UNAVAILABLE
            message = self.last_message or ""
            self.consumer.serverError(self, code, message)

    def pause(self):
        self.log("Pausing request %s", self.url)
        self.current_request.pause()

    def resume(self):
        self.log("Resuming request %s", self.url)
        self.current_request.resume()

    def cancel(self):
        self.debug("Canceling request %s", self.url)
        self.current_request.cancel()
        self.current_request = None

    def serverError(self, getter, code, message):
        self.debug("Server Error %s (%s) for %s",
                   message, code, self.url)
        self.last_error = code
        self.last_message = message
        if code in (common.SERVER_DISCONNECTED,
                    common.SERVER_TIMEOUT):
            # The connection was established
            # and data may have already been received.
            self.consumer.serverError(self, code, message)
            return
        self.current_server.reportError(code)
        self.retrieve()

    def conditionFail(self, getter, code, message):
        if self.current_request is None:
            return
        self.log("Condition Error %s (%s) for %s",
                 message, code, self.url)
        self.consumer.conditionFail(self, code, message)

    def streamNotAvailable(self, getter, code, message):
        if self.current_request is None:
            return
        self.log("Stream not available \"%s\" for %s", message, self.url)
        self.consumer.streamNotAvailable(self, code, message)

    def onInfo(self, getter, info):
        if self.current_request is None:
            return
        self.consumer.onInfo(self, info)

    def onData(self, getter, data):
        if self.current_request is None:
            return
        self.consumer.onData(self, data)

    def streamDone(self, getter):
        if self.current_request is None:
            return
        self.consumer.streamDone(self)
