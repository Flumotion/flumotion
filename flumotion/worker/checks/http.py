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


from flumotion.common import log
from flumotion.common.messages import Result
from flumotion.common.netutils import guess_public_hostname

__version__ = "$Rev$"


def runHTTPStreamerChecks():
    """Runs all the http checks
    @returns: a deferred returning a guess of the public
              hostname for this worker
    """
    # FIXME: Move over more checks from httpstreamer.py
    log.debug('httpcheck', 'Checking...')
    result = Result()
    result.succeed(guess_public_hostname())
    log.debug('httpcheck', 'done, returning')
    return result
