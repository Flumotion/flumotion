# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
import time
import errno
import resource

import gst

try:
    from twisted.web import http
except ImportError:
    from twisted.protocols import http

from twisted.web import server, resource as web_resource
from twisted.internet import reactor, defer
from flumotion.configure import configure
from flumotion.common import errors

from flumotion.common import common, log, keycards

class Logger:
    def __init__(self, args):
        self.medium = None
        self
    def setMedium(self, medium):
        self.medium = medium
    def start(self):
        pass
    def stop(self):
        pass
    def restart(self):
        self.stop()
        return self.start()
    def event(self, type, args):
        handler = getattr(self, 'event_' + type, None)
        if handler:
            handler(args)

class RequestStringToAdminLogger(StreamLogger):
    medium = None
    
    def event_http_session_completed(self, args):
        ident = '-'
        username = '-'
        date = time.strftime('%d/%b/%Y:%H:%M:%S +0000', args['time'])

        if not self.medium:
            self.warn('Told to send log messages to the admin, but no medium')

        msg = ("%s %s %s [%s] \"%s %s %s\" %d %d %s \"%s\" %d\n"
               % (args['ip'], ident, username, date,
                  args['method'], args['uri'], args['clientproto'],
                  args['response'], args['bytes-sent'], args['referer'],
                  args['user-agent'], args['time-connected']))
        # make streamer notify manager of this msg
        self.medium.sendLog(msg)
        
class ApacheLogger(StreamLogger):
    def configure(self, **kwargs):
        self.filename = kwargs['log-file-name']
        
    def start(self):
        self.file = open(

    def event_http_session_completed(self, args):
        ident = '-'
        username = '-'
        date = time.strftime('%d/%b/%Y:%H:%M:%S +0000', args['time'])

        msg = ("%s %s %s [%s] \"%s %s %s\" %d %d %s \"%s\" %d\n"
               % (args['ip'], ident, username, date,
                  args['method'], args['uri'], args['clientproto'],
                  args['response'], args['bytes-sent'], args['referer'],
                  args['user-agent'], args['time-connected']))
        self.file.write(msg)
        self.file.flush()
