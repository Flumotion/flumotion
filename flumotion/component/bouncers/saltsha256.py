# -*- Mode: Python; test-case-name: flumotion.test.test_saltsha256 -*-
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

"""
a bouncer with a username/salt/sha256 data backend
"""

import random

from twisted.internet import defer

from flumotion.common import keycards, log, errors
from flumotion.component.bouncers import component as bcomponent
from flumotion.twisted import credentials, checkers

__all__ = ['SaltSha256']
__version__ = "$Rev$"


class SaltSha256(bcomponent.ChallengeResponseBouncer):
    """
    I am a bouncer that stores usernames, salts, and SHA-256 data
    to authenticate against.
    """

    logCategory = 'passwdsaltsha256'
    keycardClasses = (keycards.KeycardUASPCC, )
    challengeResponseClasses = (keycards.KeycardUASPCC, )

    def do_setup(self):
        conf = self.config

        # we need either a filename or data
        props = conf['properties']
        filename = data = None
        if 'filename' in props:
            filename = props['filename']
            self.debug('using file %s for passwords', filename)
        elif 'data' in props:
            data = props['data']
            self.debug('using in-line data for passwords')
        else:
            return defer.fail(errors.ConfigError(
                'PasswdSaltSha256 needs either a <data> or <filename> entry'))
        # FIXME: generalize to a start method, possibly linked to mood
        if filename:
            try:
                lines = open(filename).readlines()
            except IOError, e:
                return defer.fail(errors.ConfigError(str(e)))
        else:
            lines = data.split("\n")

        self.setChecker(checkers.Sha256Checker())

        for line in lines:
            if not ':' in line:
                continue
            # when coming from a file, it ends in \n, so strip.
            # for data, we already splitted, so no \n, but strip is fine.
            name, salt, sha256Data = line.strip().split(':')
            self.addUser(name, salt, salt, sha256Data)

        self.debug('parsed %s, %d lines' % (filename or '<memory>',
            len(lines)))

        return defer.succeed(None)
