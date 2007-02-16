# -*- Mode: Python -*-
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
A test token bouncer.
"""

from twisted.internet import defer

from flumotion.common import keycards
from flumotion.component.bouncers import bouncer
from flumotion.common.keycards import KeycardToken
from flumotion.twisted import compat

__all__ = ['TokenTestBouncer']

class TokenTestBouncer(bouncer.Bouncer):

    logCategory = 'tokentestbouncer'
    keycardClasses = (KeycardToken)

    def do_setup(self):
        props = self.config['properties']
        self._authtoken = props['authorized-token']
        return defer.succeed(None)
   
    def do_authenticate(self, keycard):
        keycard_data = keycard.getData()
        self.debug('authenticating keycard from requester %s with token %s' % (
            keycard_data['address'], keycard_data['token']))

        if keycard_data['token'] == self._authtoken:
            # authenticated, so return the keycard with state authenticated
            keycard.state = keycards.AUTHENTICATED
            self.addKeycard(keycard)
            self.info('authenticated login of "%s" from ip address %s' % 
                (keycard.token, keycard.address) )
            self.debug('keycard %r authenticated, token %s ip address %s' % 
                (keycard, keycard.token, keycard.address))
            return keycard

        else:
            self.info('keycard %r unauthorized, returning None')
            return None

