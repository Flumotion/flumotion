# -*- Mode: Python -*-
# -*- Encoding: UTF-8 -*-
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

import os
import simplejson as json
import time
import socket
import traceback

from flumotion.common import python, log
from flumotion.component.plugs import request
from flumotion.component.base.http import LogFilter as logfilter
#from flumotion.component.plugs import user_agent_parser as parser

from twisted.internet import task

__version__ = "$Rev$"

def parse_user_agent(user_agent):
    """ Helper to parse user agent into mobile or pc. """

    user_agent = parser.simple_detect(user_agent)
    if "iPhone" in user_agent[0] or "Android" in user_agent[0]:
        return "mobile"
    return "pc"

class GraphiteHelper(log.Loggable):
    """ Helper to send statistics to graphite. """

    CLOSED = 'CLOSED'
    OPEN = 'OPEN'

    logName = 'graphitehelper'

    def __init__(self):
        self.state = self.CLOSED
        self.socket = None

    def open(self, server, port):
        if self.state == self.CLOSED:
            self.socket = socket.socket(socket.AF_INET,
                                        socket.SOCK_DGRAM,
                                        socket.IPPROTO_UDP)
            try:
                self.socket.connect((server, port))
                self.state = self.OPEN
                return True
            except socket.error:
                self.socket = None
                self.debug(traceback.format_exc())
            except socket.gaierror:
                self.socket = None
                self.debug(traceback.format_exc())
        return False

    def close(self):
        if self.state == self.OPEN:
            self.socket.close()
            self.socket = None
            self.state = self.CLOSED

    def send_measures(self, feed_id, user_agent, session_started=False):
        if self.state == self.OPEN:
            user_agent = parse_user_agent(user_agent)
            inc = "-1"
            if session_started:
                inc = "+1"
            message = "flumotion.streamer.%s.sessions.%s:%s|g" \
                % (feed_id, user_agent, inc)
            self.debug("Graphite DATA sent %s" % message)
            self.sent = self.socket.send(message)

STATS_SERVER = 'cassidy01dev.bt.bcn.flumotion.net'
STATS_PORT = 8125

class StreamerInfoPlug(request.RequestLoggerPlug, log.Loggable):
    """
    Base class for obtain information associated to a streamer.
    """

    logCategory = 'streamerinfo'
    activated = False

    def start(self, component):
        # Build copy of arguments.
        self.debug("Start..")

        if 'feed-id' in self.args['properties']:
            self.debug("Plugin started. Feed id -> %s" \
                % self.args['properties']['feed-id'])
            self.feed_id = self.args['properties']['feed-id']
            self.activated = True
        self.debug("starting plugin....")

        if self.activated:
            self.helper = GraphiteHelper()
            if self.helper.open(STATS_SERVER, STATS_PORT):
                self.debug('Open helper: succeeded.')
            else:
                self.debug('Open helper: failed.')

    def stop(self, component):
        # Close helper.
        self.helper.close()

    def event_http_session_completed(self, args):
        self.debug("Session completed")

        if not self.activated:
            return

        # Send metrics.
        self.helper.send_measures(self.feed_id, args['user-agent'], False)
        return

    def event_http_session_started(self, args):
        if not self.activated:
            return
        self.debug("Session started")

        # Send metrics.
        self.helper.send_measures(self.feed_id, args['user-agent'], True)
