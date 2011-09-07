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

import time


# Stream Errors
INTERNAL_ERROR = 500
NOT_IMPLEMENTED = 501
SERVER_UNAVAILABLE = 503
RANGE_NOT_SATISFIABLE = 416
STREAM_NOTFOUND = 404
STREAM_FORBIDDEN = 403
# The following error codes should only be used
# when the connection with the server has been established.
SERVER_DISCONNECTED = 502
SERVER_TIMEOUT = 504

# Condition Errors
STREAM_NOT_MODIFIED = 304
STREAM_MODIFIED = 412


class StreamConsumer(object):
    """
    Interface of the stream consumer object.
    No need to inherit from this class,
    it's here just for documentation.
    """

    def serverError(self, getter, code, message):
        pass

    def conditionFail(self, getter, code, message):
        pass

    def streamNotAvailable(self, getter, code, message):
        pass

    def onInfo(self, getter, info):
        pass

    def onData(self, getter, data):
        pass

    def streamDone(self, getter):
        pass


class StreamInfo(object):
    """
    Base stream's information container.
    No need to inherit from this class,
    it's here just for documentation.
    """
    expires = None
    mtime = None
    length = 0
    start = 0
    size = 0


class ServerInfo(object):

    def __init__(self):
        self.adress = None
        self.protocol = "http"


def log_id(obj):
    """
    Gives a unique string identifier for an instance.
    Used in the log to trace instances.
    """
    result = id(obj)
    if result < 0:
        result += 1L << 32
        if result < 0:
            # 64bit, not sure how to detect the machine address width
            result -= 1L << 32
            result += 1L << 64
            assert result > 0, "Address space fatter than 64 bits"
    result = (result << 16) + (int(time.time()) & 0xFFFF)
    return hex(result)[2:]
