# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2006 Fluendo, S.L. (www.fluendo.com).
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

"""
Wrapper for the Python SQuaLe bindings to present an interface
compatible with the Python DB-API v2.0 specification.
"""

import squale
import exceptions
import codecs
import time

# PEP 249 boilerplate
apilevel = '2.0'
threadsafety = 3
paramstyle = 'format'

STRING = BINARY = NUMBER = DATETIME = ROWID = 'string'

class Error(exceptions.StandardError):
    pass

class Warning(exceptions.StandardError):
    pass

class InterfaceError(Error):
    pass

class DatabaseError(Error):
    pass

class InternalError(DatabaseError):
    pass

class OperationalError(DatabaseError):
    pass

class ProgrammingError(DatabaseError):
    pass

class IntegrityError(DatabaseError):
    pass

class DataError(DatabaseError):
    pass

class NotSupportedError(DatabaseError):
    pass

class Date:
    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day

    def __str__(self):
        return '%04d-%02d-%02d' % (self.year, self.month, self.day)

class Time:
    def __init__(self, hour, minute, second):
        self.hour = hour
        self.minute = minute
        self.second = second

    def __str__(self):
        return '%02d:%02d:%02d' % (self.hour, self.minute, self.second)

class Timestamp:
    def __init__(self, year, month, day, hour, minute, second):
        self.date = Date(year, month, day)
        self.time = Time(hour, minute, second)

    def __str__(self):
        return '%s %s' % (self.date, self.time)

def DateFromTicks(ticks):
    return apply(Date,time.localtime(ticks)[:3])

def TimeFromTicks(ticks):
    return apply(Time,time.localtime(ticks)[3:6])

def TimestampFromTicks(ticks):
    return apply(Timestamp,time.localtime(ticks)[:6])

class Binary(str):
    pass

_escape_encoded = codecs.lookup('string_escape')[0]
def quoted_str(s):
    return '\'' + _escape_encoded(str(s))[0] + '\''

class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None
        self.description = None
        self.index = 0
        self.rowcount = 0
        self.data = []
        self.arraysize = 1

    def close(self):
        del self.result
        del self.description
        del self.rowcount
        del self.data
        del self.index
        self.connection = None

    def _set_result(self, r):
        self.description = [(name, STRING, None, None, None, None, None)
                            for name in r.get_column_names()]
        if r.get_status() == squale.RESULT_RESULTSET:
            self.data = r.get_data()
        else:
            self.data = []
        self.index = 0
        self.rowcount = len(self.data)
        
    def execute(self, operation, parameters=None):
        if hasattr(parameters, 'keys'):
            raise NotSupportedError('SQuaLe does not support named '
                                    'parameters (dicts)')
        
        if parameters:
            parameters = tuple([quoted_str(x) for x in parameters])
            sql = operation % parameters
        else:
            sql = operation
        try:
            r = squale.Result(self.connection.name, sql)
        except squale.SqualeError, e:
            raise Error(*e.args)
        self._set_result(r)

    def executemany(self, operation, parameters):
        for p in parameters:
            self.execute(operation, p)

    def fetchone(self):
        if not self.rowcount:
            raise DataError('no results')

        if self.index < self.rowcount:
            ret = self.data[self.index]
            self.index += 1
        else:
            ret = None

        return ret

    def fetchmany(self, size=None):
        if not self.rowcount:
            raise DataError('no results')

        _count = self.rowcount - self.index
        if not size:
            size = self.arraysize
        _count = min(size, _count)
        ret = self.data[self.index:self.index+_count]
        self.index += _count
        return ret
            
    def fetchall(self):
        if not self.rowcount:
            raise DataError('no results')

        ret = self.data[self.index:self.rowcount]
        self.index = self.rowcount
        return ret

    def setinputsizes(self, sizes):
        pass

    def setoutputsizes(self, sizes, column=None):
        pass

class Connection:
    def __init__(self, connection_name):
        self.name = connection_name

    def commit(self):
        pass

    def cursor(self):
        return Cursor(self)

    def close(self):
        self.name = None

def connect(connection_name):
    return Connection(connection_name)
