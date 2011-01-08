# -*- Mode: Python; test-case-name: flumotion.test.test_htpasswdcrypt -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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
an htpasswd-backed bouncer with crypt passwords
"""

import random

from twisted.internet import defer

from flumotion.common import keycards, log, errors
from flumotion.component.bouncers import component as bcomponent
from flumotion.twisted import credentials, checkers

__all__ = ['HTPasswdCrypt']
__version__ = "$Rev$"


class HTPasswdCrypt(bcomponent.ChallengeResponseBouncer):

    logCategory = 'htpasswdcrypt'
    # challenger type first, because it's more secure thus preferable
    keycardClasses = (keycards.KeycardUACPCC, keycards.KeycardUACPP)
    challengeResponseClasses = (keycards.KeycardUACPCC, )

    def do_setup(self):
        conf = self.config

        # we need either a filename or data
        filename = None
        data = None
        props = conf['properties']
        if 'filename' in props:
            filename = props['filename']
            self.debug('using file %s for passwords', filename)
        elif 'data' in props:
            data = props['data']
            self.debug('using in-line data for passwords')
        else:
            return defer.fail(errors.ConfigError(
                'HTPasswdCrypt needs either a <data> or <filename> entry'))
        # FIXME: generalize to a start method, possibly linked to mood
        if filename:
            try:
                lines = open(filename).readlines()
            except IOError, e:
                return defer.fail(errors.ConfigError(str(e)))
        else:
            lines = data.split("\n")

        self.setChecker(checkers.CryptChecker())
        for line in lines:
            if not ':' in line:
                continue
            # when coming from a file, it ends in \n, so strip.
            # for data, we already splitted, so no \n, but strip is fine.
            name, cryptPassword = line.strip().split(':')
            self.addUser(name, cryptPassword[:2], cryptPassword)

        self.debug('parsed %s, %d lines' % (filename or '<memory>',
            len(lines)))

        return defer.succeed(None)
