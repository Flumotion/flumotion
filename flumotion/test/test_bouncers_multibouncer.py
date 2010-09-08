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
from flumotion.component import component
from flumotion.component.bouncers import multibouncer, multibouncerplug
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


class MultiBouncerTestCase(object):
    """This is test case both for MultiBouncer and MultiBouncerPlug"""

    def _testCase(self, *a):
        raise NotImplementedError("Not impleneted error")

    def setUp(self):
        keycard = keycards.KeycardGeneric()
        keycard.username = 'user'
        keycard.password = 'test'
        keycard.address = '62.121.66.134'
        self.keycard = keycard

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


class TestMultiBouncerPlug(bouncertest.BouncerTestHelper,\
        MultiBouncerTestCase):

    setUp = MultiBouncerTestCase.setUp

    def _getComponentAndBouncer(self, combination):

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

        bouncer_props = {'name': 'testbouncer',
                'plugs': {},
                'properties': {'combination': combination}}
        component_props = {'name': 'component',
                'plugs': plugs,
                'properties': {}}

        comp = component.BaseComponent(component_props)
        bouncer = multibouncerplug.MultiBouncerPlug(bouncer_props)
        bouncer.start(comp)
        return comp, bouncer

    def stop_bouncer(self, bouncer, d, component):

        def _stop(res):
            bouncer.stop(component)
            return res
        return d.addBoth(_stop)

    def _testCase(self, combination, result):
        component, bouncer = self._getComponentAndBouncer(combination)
        d = self.check_auth(self.keycard, bouncer, result)
        return self.stop_bouncer(bouncer, d, component)


class TestMultiBouncer(bouncertest.BouncerTestHelper, MultiBouncerTestCase):

    setUp = MultiBouncerTestCase.setUp

    def _testCase(self, combination, result):
        bouncer = self._getBouncer(combination)
        d = self.check_auth(self.keycard, bouncer, result)
        return self.stop_bouncer(bouncer, d)

    def _getBouncer(self, combination):

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
