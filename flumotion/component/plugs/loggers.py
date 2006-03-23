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

import time

from twisted.python import reflect

from flumotion.common import errors, log


class Logger(log.Loggable):
    """
    Base class for logger implementations. Defines the logger API
    methods.
    """
    def __init__(self, args):
        self.args = args

    def start(self, component):
        pass

    def stop(self, component):
        pass

    def restart(self, component):
        self.stop(component)
        self.start(component)

    def event(self, type, args):
        handler = getattr(self, 'event_' + type, None)
        if handler:
            handler(args)

def _http_session_completed_to_apache_log(args):
    ident = '-'
    username = '-'
    date = time.strftime('%d/%b/%Y:%H:%M:%S +0000', args['time'])

    return ("%s %s %s [%s] \"%s %s %s\" %d %d %s \"%s\" %d\n"
            % (args['ip'], ident, username, date,
               args['method'], args['uri'], args['clientproto'],
               args['response'], args['bytes-sent'], args['referer'],
               args['user-agent'], args['time-connected']))

class RequestStringToAdminLogger(Logger):
    """
    Logger for passing apache-style request strings to the admin
    """

    medium = None
    
    def start(self, component):
        self.medium = component.medium

    def event_http_session_completed(self, args):
        if not self.medium:
            self.warning('Told to send log messages to the admin, '
                         'but no medium')

        # notify admin of this msg via the manager
        self.medium.callRemote('adminCallRemote', 'logMessage',
                               _http_session_completed_to_apache_log(args))
        
class ApacheLogger(Logger):
    filename = None
    file = None

    def start(self, component):
        self.filename = self.args['properties']['logfile']
        try:
            self.file = open(self.filename, 'a')
        except IOError, data:
            raise errors.PropertiesError('could not open log file %s '
                                         'for writing (%s)'
                                         % (self.filename, data[1]))

    def stop(self, component):
        self.file.close()
        self.file = None

    def event_http_session_completed(self, args):
        self.file.write(_http_session_completed_to_apache_log(args))
        self.file.flush()

class DatabaseLogger(Logger):
    module = None
    connection = None
    operation = None
    sql_template = ("insert into %s (ip, session_time, session_duration, "
                    "session_bytes, user_agent, referrer) "
                    "values (%%s, %%s, %%s, %%s, %%s, %%s)")
    sql = None

    translators = {'MySQLdb': {'password': 'passwd',
                               'database': 'db'}}

    def start(self, component):
        props = self.args['properties']

        modulename = props['database-module']
        module = reflect.namedModule(modulename)

        translator = self.translators.get(modulename, {})

        kwargs = {}
        for k in ('user', 'password', 'host', 'port', 'connect-timeout',
                  'database'):
            if k in props:
                kwargs[translator.get(k,k)] = props[k]
        c = module.connect(**kwargs)

        self.sql = self.sql_template % props.get('table', 'stream')
        self.module = module
        self.connection = c
        self.cursor = c.cursor()

    def stop(self, component):
        self.cursor.close()
        self.cursor = None
        self.connection.close()
        self.connection = None
        self.module = None

    def event_http_session_completed(self, args):
        self.cursor.execute(self.sql,
                            (args['ip'],
                             self.module.Timestamp(*args['time'][:6]),
                             args['time-connected'],
                             args['bytes-sent'],
                             args['user-agent'],
                             args['referer']))
