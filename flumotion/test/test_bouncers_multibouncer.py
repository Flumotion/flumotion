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

from twisted.internet import defer

from flumotion.common import testsuite

from flumotion.common import keycards
from flumotion.common.planet import moods
from flumotion.component.bouncers import multibouncer
from flumotion.component.bouncers import base as bouncers_base
from flumotion.component.bouncers.algorithms import base

from flumotion.test import bouncertest


class RejectingPlug(base.BouncerAlgorithm):

    def authenticate(self, keycard):
        return None


class AcceptingPlug(base.BouncerAlgorithm):

    def authenticate(self, keycard):
        keycard.state = keycards.AUTHENTICATED
        return keycard


def _get_bouncer(combination):

    def plugStructure(module, function):
        socket = ".".join([module, function])
        return \
            {'type': function,
             'socket': socket,
             'entries': {'default':
                   {'function-name': function,
                    'module-name': module}},
             'properties': {}}

    plugs = {bouncers_base.BOUNCER_ALGORITHM_SOCKET:
                [plugStructure('flumotion.test.test_bouncers_multibouncer', \
                    'AcceptingPlug'),
                 plugStructure('flumotion.test.test_bouncers_multibouncer', \
                    'RejectingPlug')]}

    props = {'name': 'testbouncer',
             'plugs': plugs,
             'properties': {'combination': combination}}
    return multibouncer.MultiBouncer(props)


class TestMultiBouncer(bouncertest.BouncerTestHelper):

    def setUp(self):
        keycard = keycards.KeycardGeneric()
        keycard.username = 'user'
        keycard.password = 'test'
        keycard.address = '62.121.66.134'
        self.keycard = keycard

    def _testCase(self, combination, result):
        bouncer = _get_bouncer(combination)
        d = self.check_auth(self.keycard, bouncer, result)
        return self.stop_bouncer(bouncer, d)

    def testAndOperatorTrue(self):
        return self._testCase('AcceptingPlug and AcceptingPlug', True)

    def testAndOperatorFalse(self):
        return self._testCase('AcceptingPlug and RejectingPlug', False)

    def testAndOperator3Bouncers(self):
        return self._testCase(\
            'AcceptingPlug and AcceptingPlug and RejectingPlug', False)

    def testNotOperator(self):
        return self._testCase('not AcceptingPlug', False)

    def testOrOperatorFalse(self):
        return self._testCase('RejectingPlug or RejectingPlug', False)

    def testOrOperatorTrue(self):
        return self._testCase('AcceptingPlug or RejectingPlug', True)
