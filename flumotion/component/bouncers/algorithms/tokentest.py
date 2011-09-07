# -*- Mode: Python; test-case-name: flumotion.test.test_bouncers_ipbouncer -*-
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
A test token bouncer.
"""

from flumotion.common import keycards
from flumotion.component.bouncers.algorithms import base

__version__ = "$Rev$"


class TokenTestAlgorithm(base.BouncerAlgorithm):

    logCategory = 'tokentestbouncer'
    volatile = False

    def get_namespace(self):
        return 'tokentest'

    def start(self, component):
        self._authtoken = self.args['properties']['authorized-token']

    def authenticate(self, keycard):
        keycard_data = keycard.getData()
        self.debug('authenticating keycard from requester %s with token %s',
                   keycard_data['address'], keycard_data['token'])

        if keycard_data['token'] == self._authtoken:
            # authenticated, so return the keycard with state authenticated
            keycard.state = keycards.AUTHENTICATED
            self.info('authenticated login of "%s" from ip address %s',
                      keycard.token, keycard.address)
            return keycard

        keycard.state = keycards.REFUSED
        self.info('keycard %r unauthorized, returning None', keycard)
        return None
