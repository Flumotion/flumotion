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

from flumotion.common import testsuite

from twisted.internet import defer, reactor

from flumotion.common import keycards


class BouncerTestHelper(testsuite.TestCase):

    bouncerClass = None

    def _generate_config(self, properties):
        conf = {'name': 'fake',
                'avatarId': '/default/fake',
                'plugs': {},
                'properties': properties}
        return conf

    def get_bouncer(self, properties={}):
        if not self.bouncerClass:
            raise NotImplemented("Subclass should set bouncerClass")
        return self.bouncerClass(self._generate_config(properties))

    def stop_bouncer(self, bouncer, d):

        def _stop(res):
            bouncer.stop()
            return res
        return d.addBoth(_stop)

    def check_auth(self, keycard, bouncer, successful):

        def check_result(result):
            if successful:
                self.assertEquals(result.state, keycards.AUTHENTICATED)
            else:
                self.assertIdentical(result, None)
        d = defer.maybeDeferred(bouncer.authenticate, keycard)
        d.addCallback(check_result)
        return d
