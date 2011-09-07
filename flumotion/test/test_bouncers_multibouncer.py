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

from twisted.internet import defer

from flumotion.common import testsuite

from flumotion.common import keycards, errors
from flumotion.common.planet import moods
from flumotion.component import component
from flumotion.component.base import http
from flumotion.component.bouncers import multibouncer, multibouncerplug, \
                                         combinator
from flumotion.component.bouncers import base as bouncers_base
from flumotion.component.bouncers.algorithms import base

from flumotion.test import bouncertest

import pyparsing


class RejectingPlug(base.BouncerAlgorithm):

    def authenticate(self, keycard):
        return None


class AcceptingPlug(base.BouncerAlgorithm):

    def authenticate(self, keycard):
        keycard.state = keycards.AUTHENTICATED
        return keycard


class MultiBouncerTestHelper(object):
    """This is a helper used by both testcases to simulate
    the job of the registery.
    Basicaly I need this to use my own bouncer mocks"""

    def plugStructure(self, module, function, properties={}):
        socket = ".".join([module, function])
        return \
            {'type': function,
            'socket': socket,
            'entries': {'default':
                {'function-name': function,
                    'module-name': module}},
            'properties': properties}

    def _plugsAcceptingRejectingAndMulti(self, combination):
        plugs = self._plugsAcceptingAndRejecting()
        return self._addMultibouncerPlug(plugs, combination)

    def _addMultibouncerPlug(self, plugs, combination):
        plugSocket = 'flumotion.component.bouncers.multibouncerplug'
        plugs[bouncers_base.BOUNCER_SOCKET] = \
            [self.plugStructure(plugSocket,
             'MultiBouncerPlug', {'combination': combination})]
        return plugs

    def _plugsAcceptingAndRejecting(self):
        module = 'flumotion.test.test_bouncers_multibouncer'
        return \
            {bouncers_base.BOUNCER_ALGORITHM_SOCKET:
                [self.plugStructure(module, 'AcceptingPlug'),
                 self.plugStructure(module, 'RejectingPlug')]}

    def _plugsTwiceAccepting(self):
        module = 'flumotion.test.test_bouncers_multibouncer'
        return \
            {bouncers_base.BOUNCER_ALGORITHM_SOCKET:
                [self.plugStructure(module, 'AcceptingPlug'),
                 self.plugStructure(module, 'AcceptingPlug')]}

    def _plugsTwiceAcceptingAndMulti(self, combination):
        plugs = self._plugsTwiceAccepting()
        return self._addMultibouncerPlug(plugs, combination)


class MultiBouncerTestCase(object):
    """This is test case run both agains for
    MultiBouncer and MultiBouncerPlug"""

    def _testCase(self, *a):
        raise NotImplementedError("Not implemented error")

    def _testForFailure(self, *a):
        raise NotImplementedError("Not implenented error")

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

    def testEmptyCombination(self):
        self._testForFailure("", 'wrong-combination')

    def testUnknownPlugins(self):
        self._testForFailure("something and something-else",
            'wrong-combination')

    def testMissingPyparsing(self):
        combinator.pyparsing = None
        self._testForFailure("AcceptingPlug", 'missing-pyparsing')
        combinator.pyparsing = pyparsing


class TestMultiBouncerPlug(bouncertest.BouncerTestHelper,\
        MultiBouncerTestCase, MultiBouncerTestHelper):

    setUp = MultiBouncerTestCase.setUp

    def _buildComponent(self, plugs):
        return {'name': 'component',
                'plugs': plugs,
                'properties': {}}

    def _getComponentAndBouncer(self, combination):
        plugs = self._plugsAcceptingRejectingAndMulti(combination)
        comp = component.BaseComponent(self._buildComponent(plugs))
        return comp, self._extractBouncerPlug(comp)

    def _extractBouncerPlug(self, comp):
        http_auth = http.HTTPAuthentication(comp)
        return http_auth.plug

    def stop_bouncer(self, bouncer, d, component):

        def _stop(res):
            bouncer.stop(component)
            return res
        return d.addBoth(_stop)

    def _testCase(self, combination, result):
        component, bouncer = self._getComponentAndBouncer(combination)
        bouncer.start(component)
        d = self.check_auth(self.keycard, bouncer, result)
        return self.stop_bouncer(bouncer, d, component)

    def _testForFailure(self, combination, message_id, custom_component=None):

        def doAsserts(d):
            self.assertEqual(component.getMood(), moods.sad.value)
            self.debug(component.state.get('messages'))
            self.assertEqual(component.state.get('messages')[0].id, message_id)

        if custom_component:
            component = custom_component
            bouncer = self._extractBouncerPlug(component)
        else:
            component, bouncer = self._getComponentAndBouncer(combination)
        d = defer.maybeDeferred(bouncer.start, component)
        d.addBoth(doAsserts)

    def testEmptyPlugs(self):
        plugs = self._addMultibouncerPlug({}, "")
        componentProps = self._buildComponent(plugs)
        comp = component.BaseComponent(componentProps)
        self._testForFailure("", 'no-algorithm', custom_component=comp)

    def testAddingSuffixes(self):
        plugs = self._plugsTwiceAcceptingAndMulti(
            "AcceptingPlug and AcceptingPlug-1")
        componentProps = self._buildComponent(plugs)
        comp = component.BaseComponent(componentProps)
        bouncer = self._extractBouncerPlug(comp)
        d = self.check_auth(self.keycard, bouncer, True)
        return self.stop_bouncer(bouncer, d, comp)

    def testExpringKeycard(self):
        plugs = self._plugsAcceptingRejectingAndMulti("AcceptingPlug")
        componentProps = self._buildComponent(plugs)
        comp = component.BaseComponent(componentProps)
        # mock method instead using HTTPStreamer
        comp.remove_client = callable
        http_auth = http.HTTPAuthentication(comp)
        bouncer = http_auth.plug
        self.keycard._fd = 100

        d = self.check_auth(self.keycard, bouncer, True)
        # theese values would be set by the proper
        # request authentication by HTTPStreamer
        http_auth._idToKeycard[self.keycard.id] = self.keycard
        http_auth._fdToKeycard[self.keycard._fd] = self.keycard

        d.addCallback(lambda _:
            self.assertIn(self.keycard.id, http_auth._idToKeycard))
        d.addCallback(lambda _: bouncer.expireKeycardId(self.keycard.id))
        d.addCallback(lambda _:
            self.assertNotIn(self.keycard.id, http_auth._idToKeycard))
        return self.stop_bouncer(bouncer, d, comp)


class TestMultiBouncer(bouncertest.BouncerTestHelper,\
            MultiBouncerTestCase, MultiBouncerTestHelper):

    setUp = MultiBouncerTestCase.setUp

    def _testCase(self, combination, result):
        bouncer = self._getBouncer(combination)
        d = self.check_auth(self.keycard, bouncer, result)
        return self.stop_bouncer(bouncer, d)

    def _getBouncer(self, combination):
        return multibouncer.MultiBouncer(self._buildBouncer(combination))

    def _buildBouncer(self, combination):

        plugs = self._plugsAcceptingAndRejecting()
        props = {'name': 'testbouncer',
                'plugs': plugs,
                'properties': {'combination': combination}}

        return props

    def _testForFailure(self, combination, message_id, custom_bouncer=None):

        def doAsserts(d):
            self.assertEqual(bouncer.getMood(), moods.sad.value)
            self.debug(bouncer.state.get('messages'))
            self.assertEqual(bouncer.state.get('messages')[0].id, message_id)

        if custom_bouncer:
            bouncer = custom_bouncer
        else:
            bouncer = self._getBouncer(combination)
        d = bouncer.waitForHappy()
        d.addBoth(doAsserts)

    def testEmptyPlugs(self):
        bouncerProps = self._buildBouncer("")
        bouncerProps['plugs'] = {}
        bouncer = multibouncer.MultiBouncer(bouncerProps)
        self._testForFailure("", 'no-algorithm', custom_bouncer=bouncer)

    def testAddingSuffixes(self):
        bouncerProps = self._buildBouncer("AcceptingPlug and AcceptingPlug-1")
        bouncerProps['plugs'] = self._plugsTwiceAccepting()
        bouncer = multibouncer.MultiBouncer(bouncerProps)
        d = self.check_auth(self.keycard, bouncer, True)
        return self.stop_bouncer(bouncer, d)

    def testExpringKeycard(self):
        bouncer = self._getBouncer("AcceptingPlug")

        d = self.check_auth(self.keycard, bouncer, True)
        d.addCallback(lambda _:
            self.assertIn(self.keycard.id, bouncer.watchable_keycards))
        d.addCallback(lambda _: bouncer.expireKeycardId(self.keycard.id))
        d.addCallback(lambda _:
            self.assertNotIn(self.keycard.id, bouncer.watchable_keycards))
        return self.stop_bouncer(bouncer, d)
