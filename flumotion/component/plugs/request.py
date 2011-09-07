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

from flumotion.common import errors
from flumotion.component.plugs import base

__version__ = "$Rev$"


class RequestLoggerPlug(base.ComponentPlug):
    """
    Base class for logger implementations. Should be renamed to
    StreamLogger later...
    """

    def event(self, type, args):
        """
        Handle a log event.

        This dispatches a particular event type such as
        "http_session_completed" to a method "event_http_session_completed".

        Returns a Deferred (which will fire once the event handling has been
        completed), or None.
        """
        handler = getattr(self, 'event_' + type, None)
        if handler:
            return handler(args)

    def rotate(self):
        # do nothing by default
        pass


def _http_session_completed_to_apache_log(args):
    # ident is something that should in theory come from identd but in
    # practice is never there
    ident = '-'
    date = time.strftime('%d/%b/%Y:%H:%M:%S +0000', args['time'])

    return ("%s %s %s [%s] \"%s %s %s\" %d %d %s \"%s\" %d\n"
            % (args['ip'], ident, args['username'], date,
               args['method'], args['uri'], args['clientproto'],
               args['response'], args['bytes-sent'], args['referer'],
               args['user-agent'], args['time-connected']))


class RequestLoggerFilePlug(RequestLoggerPlug):
    filename = None
    file = None

    def start(self, component=None):
        self.filename = self.args['properties']['logfile']
        try:
            self.file = open(self.filename, 'a')
        except IOError, data:
            raise errors.PropertyError('could not open log file %s '
                                         'for writing (%s)'
                                         % (self.filename, data[1]))

    def stop(self, component=None):
        if self.file:
            self.file.close()
            self.file = None

    def event_http_session_completed(self, args):
        self.file.write(_http_session_completed_to_apache_log(args))
        self.file.flush()

    def rotate(self):
        self.stop()
        self.start()
