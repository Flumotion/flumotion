# -*- Mode: Python; -*-
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


HAS_MODULES = False
try:
    from icalendar import vDatetime
    from dateutil import tz
    HAS_MODULES = True
except ImportError:
    pass

import os
import tempfile
from datetime import datetime, timedelta

from flumotion.common import testsuite
from twisted.trial import unittest
from twisted.internet import defer

from flumotion.common import keycards
from flumotion.common.planet import moods
from flumotion.component.bouncers import icalbouncer

from flumotion.common import eventcalendar


def _get_config(path=None):
    props = {'name': 'testbouncer',
             'plugs': {},
             'properties': {}}
    if path:
        props['properties']['file'] = path

    return props


class RequiredModulesMixin(object):
    if not HAS_MODULES:
        skip = 'This test requires the icalendar and dateutil modules'


class TestIcalBouncerSetup(testsuite.TestCase, RequiredModulesMixin):

    def setUp(self):
        self.bouncer = None
        self.path = os.path.join(os.path.split(__file__)[0],
                                 'test-google.ics')

    def tearDown(self):
        if self.bouncer:
            self.bouncer.stop()

    def testNoFileProperty(self):
        conf = _get_config()
        self.bouncer = icalbouncer.IcalBouncer(conf)
        self.assertEquals(self.bouncer.getMood(), moods.sad.value)

    def testNonexistentIcalFile(self):
        conf = _get_config('/you/dont/have/that/file')
        self.bouncer = icalbouncer.IcalBouncer(conf)
        self.assertEquals(self.bouncer.getMood(), moods.sad.value)

    def testMalformedIcalFile(self):
        conf = _get_config(__file__)
        self.bouncer = icalbouncer.IcalBouncer(conf)
        self.assertEquals(self.bouncer.getMood(), moods.sad.value)

    def testSuccessfulSetup(self):
        conf = _get_config(self.path)
        self.bouncer = icalbouncer.IcalBouncer(conf)
        self.assertEquals(self.bouncer.getMood(), moods.happy.value)


class TestIcalBouncerRunning(testsuite.TestCase, RequiredModulesMixin):

    def setUp(self):
        self.bouncer = None
        self.now = datetime.now(eventcalendar.UTC)
        self.a_day_ago = self.now - timedelta(days=1)
        self.half_an_hour_ago = self.now - timedelta(minutes=30)
        self.in_half_an_hour = self.now + timedelta(minutes=30)
        self.ical_template = """
BEGIN:VCALENDAR
PRODID:-//Flumotion Fake Calendar Creator//flumotion.com//
VERSION:2.0
BEGIN:VEVENT
DTSTART%(dtstart-tzid)s:%(dtstart)s
DTEND%(dtend-tzid)s:%(dtend)s
SUMMARY:Test calendar
UID:uid
END:VEVENT
END:VCALENDAR
"""

    def tearDown(self):
        if self.bouncer:
            self.bouncer.stop()

    def bouncer_from_ical(self, data):
        tmp = tempfile.NamedTemporaryFile()
        tmp.write(data)
        tmp.flush()
        conf = _get_config(tmp.name)
        return icalbouncer.IcalBouncer(conf)

    def ical_from_specs(self, dtstart_tzid, dtstart, dtend_tzid, dtend):
        return self.ical_template % {'dtstart-tzid': dtstart_tzid,
                                     'dtstart': vDatetime(dtstart).ical(),
                                     'dtend-tzid': dtend_tzid,
                                     'dtend': vDatetime(dtend).ical()}

    def _approved_callback(self, keycard):
        self.failUnless(keycard)
        self.assertEquals(keycard.state, keycards.AUTHENTICATED)

    def _denied_callback(self, keycard):
        self.failIf(keycard)


class TestIcalBouncerUTC(TestIcalBouncerRunning, RequiredModulesMixin):

    def testDeniedUTC(self):
        data = self.ical_from_specs('', self.a_day_ago,
                                    '', self.half_an_hour_ago)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._denied_callback)
        return d

    def testApprovedUTC(self):
        data = self.ical_from_specs('', self.a_day_ago,
                                    '', self.in_half_an_hour)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._approved_callback)
        return d


class TestIcalBouncerTZID(TestIcalBouncerRunning, RequiredModulesMixin):

    def setUp(self):
        TestIcalBouncerRunning.setUp(self)
        # Beijing is UTC+8
        self.beijing_tz = tz.gettz('Asia/Shanghai')
        if self.beijing_tz is None:
            raise unittest.SkipTest("Could not find tzinfo data "
                                    "for the Asia/Shanghai timezone")
        # Guatemala is UTC+8
        self.guatemala_tz = tz.gettz('America/Guatemala')
        if self.guatemala_tz is None:
            raise unittest.SkipTest("Could not find tzinfo data "
                                    "for the America/Guatemala timezone")

    def testIncorrectTimeTZID(self):
        naive_new_end = self.in_half_an_hour.replace(tzinfo=None)

        # This will fail the assertion that an event can't start after
        # it ended (if our timezone handling is correct)
        data = self.ical_from_specs('', self.half_an_hour_ago,
                                    ';TZID=Asia/Shanghai', naive_new_end)
        self.bouncer = self.bouncer_from_ical(data)

        self.assertEquals(self.bouncer.getMood(), moods.sad.value)

    def testDeniedTZID(self):
        new_end = self.half_an_hour_ago.astimezone(self.beijing_tz)
        naive_new_end = new_end.replace(tzinfo=None)

        data = self.ical_from_specs('', self.a_day_ago,
                                    ';TZID=Asia/Shanghai', naive_new_end)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._denied_callback)
        return d

    def testApprovedBothTZID(self):
        new_start = self.half_an_hour_ago.astimezone(self.beijing_tz)
        naive_new_start = new_start.replace(tzinfo=None)
        new_end = self.in_half_an_hour.astimezone(self.guatemala_tz)
        naive_new_end = new_end.replace(tzinfo=None)

        data = self.ical_from_specs(';TZID=Asia/Shanghai', naive_new_start,
                                    ';TZID=America/Guatemala', naive_new_end)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._approved_callback)
        return d

    def testApprovedKeycardDurationCalculationTZID(self):
        in_one_minute = datetime.now(self.beijing_tz) + timedelta(minutes=1)
        naive_in_one_minute = in_one_minute.replace(tzinfo=None)

        data = self.ical_from_specs('', self.a_day_ago,
                                    ';TZID=Asia/Shanghai', naive_in_one_minute)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        def approved_and_calculate(result):
            self.failUnless(result)
            self.assertEquals(result.state, keycards.AUTHENTICATED)
            self.failUnless(result.duration)
            self.failIf(result.duration > 60)
        d.addCallback(approved_and_calculate)
        return d


class TestIcalBouncerFloating(TestIcalBouncerRunning, RequiredModulesMixin):

    def testApprovedBothFloating(self):
        new_start = self.half_an_hour_ago.astimezone(eventcalendar.LOCAL)
        new_end = self.in_half_an_hour.astimezone(eventcalendar.LOCAL)
        new_start_naive = new_start.replace(tzinfo=None)
        new_end_naive = new_end.replace(tzinfo=None)

        data = self.ical_from_specs('', new_start_naive,
                                    '', new_end_naive)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._approved_callback)
        return d

    def testDeniedUTCAndFloating(self):
        new_start = self.a_day_ago.astimezone(eventcalendar.LOCAL)
        new_start_naive = new_start.replace(tzinfo=None)

        data = self.ical_from_specs('', new_start_naive,
                                    '', self.half_an_hour_ago)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._denied_callback)
        return d

    def testApprovedTZFromEnvironmentWithFloating(self):
        new_end_naive = self.half_an_hour_ago.replace(tzinfo=None)
        os.environ['TZ'] = 'UTC+%d' % 1
        data = self.ical_from_specs('', self.half_an_hour_ago,
                                    '', new_end_naive)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._approved_callback)
        return d
