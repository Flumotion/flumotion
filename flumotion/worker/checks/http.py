# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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
