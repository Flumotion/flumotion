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
from flumotion.component.bouncers.algorithms import icalbouncer as \
    icalbounceralgorithm
from flumotion.component.base import scheduler

from flumotion.common import eventcalendar


def _get_config(path=None):
    props = {'name': 'testbouncer',
             'plugs': {},
             'properties': {}}
    if path:
        props['properties']['file'] = path

    return props


def get_iCalScheduler(bouncer):
    return bouncer.get_main_algorithm().iCalScheduler


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
BEGIN:VTIMEZONE
TZID:Asia/Shanghai
BEGIN:STANDARD
TZOFFSETFROM:+0800
TZOFFSETTO:+0800
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VTIMEZONE
TZID:America/Guatemala
BEGIN:STANDARD
TZOFFSETFROM:-0600
TZOFFSETTO:-0600
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE
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

    def testDeniedIfNotDefinedTZID(self):
        new_end = self.half_an_hour_ago.astimezone(self.beijing_tz)
        naive_new_end = new_end.replace(tzinfo=None)

        data = self.ical_from_specs('', self.a_day_ago,
                                    ';TZID=/some/obscure/path/Asia/Shanghai',
                                    naive_new_end)
        try:
            self.bouncer = self.bouncer_from_ical(data)
        except NotCompilantError:
            pass
        else:
            self.assert_(True)

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

        def _restoreTZEnv(result, oldTZ):
            if oldTZ is None:
                del os.environ['TZ']
            else:
                os.environ['TZ'] = oldTZ
            return result

        new_end_naive = self.half_an_hour_ago.replace(tzinfo=None)

        oldTZ = os.environ.get('TZ', None)
        os.environ['TZ'] = 'US/Pacific'

        data = self.ical_from_specs('', self.half_an_hour_ago,
                                    '', new_end_naive)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)
        d.addCallback(self._approved_callback)
        d.addBoth(_restoreTZEnv, oldTZ)
        return d


class TestIcalBouncerOverlap(testsuite.TestCase, RequiredModulesMixin):

    def setUp(self):
        self.bouncer = None
        self.now = datetime.now(eventcalendar.UTC)
        td = icalbounceralgorithm.IcalBouncerAlgorithm.maxKeyCardDuration
        self.maxKeyCardDuration = max(td.days * 24 * 60 * 60 + td.seconds + \
                                            td.microseconds / 1e6, 0)
        self.ical_template = """
BEGIN:VCALENDAR
PRODID:-//Flumotion Fake Calendar Creator//flumotion.com//
VERSION:2.0
BEGIN:VEVENT
DTSTART:%(dtstart1)s
DTEND:%(dtend1)s
SUMMARY:Test calendar
UID:uid1
END:VEVENT

BEGIN:VEVENT
DTSTART:%(dtstart2)s
DTEND:%(dtend2)s
SUMMARY:Test calendar
UID:uid2
END:VEVENT

BEGIN:VEVENT
DTSTART:%(dtstart3)s
DTEND:%(dtend3)s
SUMMARY:Test calendar
UID:uid3
END:VEVENT
END:VCALENDAR
"""

    def tearDown(self):
        if self.bouncer:
            self.bouncer.stop()

    def ical_from_specs(self, dates):
        return self.ical_template % {'dtstart1': vDatetime(dates[0]).ical(),
                                     'dtend1': vDatetime(dates[1]).ical(),
                                     'dtstart2': vDatetime(dates[2]).ical(),
                                     'dtend2': vDatetime(dates[3]).ical(),
                                     'dtstart3': vDatetime(dates[4]).ical(),
                                     'dtend3': vDatetime(dates[5]).ical(),
                                     }

    def _denied_callback(self, keycard):
        self.failIf(keycard)

    def _approved_and_calculate(self, result, target):
        self.failUnless(result)
        self.assertEquals(result.state,
        keycards.AUTHENTICATED)
        self.failUnless(result.duration)
        self.failUnless(target - 30 < result.duration < target + 30)

    def bouncer_from_ical(self, data):
        tmp = tempfile.NamedTemporaryFile()
        tmp.write(data)
        tmp.flush()
        conf = _get_config(tmp.name)
        return icalbouncer.IcalBouncer(conf)

    def _timedeltaToSeconds(self, td):
        return max(td.days * 24 * 60 * 60 + td.seconds + \
                                    td.microseconds / 1e6, 0)

    def testOverlapLessThanWindowSize(self):
        dates = [self.now - timedelta(minutes=1),
            self.now + timedelta(seconds=0.4*self.maxKeyCardDuration),
            self.now + timedelta(seconds=0.2*self.maxKeyCardDuration),
            self.now + timedelta(seconds=0.6*self.maxKeyCardDuration),
            self.now + timedelta(seconds=0.4*self.maxKeyCardDuration),
            self.now + timedelta(seconds=0.8*self.maxKeyCardDuration),
        ]
        data = self.ical_from_specs(dates)
        self.bouncer = self.bouncer_from_ical(data)
        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)


        d.addCallback(self._approved_and_calculate,\
                                    0.8*self.maxKeyCardDuration)
        return d

    def testOverlapMoreThanWindowSize(self):
        dates = [self.now - timedelta(minutes=1),
            self.now + timedelta(seconds=0.6*self.maxKeyCardDuration),
            self.now + timedelta(seconds=0.3*self.maxKeyCardDuration),
            self.now + timedelta(seconds=0.9*self.maxKeyCardDuration),
            self.now + timedelta(seconds=0.6*self.maxKeyCardDuration),
            self.now + timedelta(seconds=1.2*self.maxKeyCardDuration),
        ]
        data = self.ical_from_specs(dates)
        self.bouncer = self.bouncer_from_ical(data)
        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        d.addCallback(self._approved_and_calculate, self.maxKeyCardDuration)
        return d

    def testOverlapEndingSimulteanously(self):
        dates = [self.now - timedelta(minutes=1),
            self.now + timedelta(seconds=0.6*self.maxKeyCardDuration),
            self.now - timedelta(minutes=2),
            self.now + timedelta(seconds=0.6*self.maxKeyCardDuration),
            self.now - timedelta(seconds=10),
            self.now - timedelta(seconds=1),
        ]
        data = self.ical_from_specs(dates)
        self.bouncer = self.bouncer_from_ical(data)
        keycard = keycards.KeycardGeneric()
        d = defer.maybeDeferred(self.bouncer.authenticate, keycard)

        d.addCallback(self._approved_and_calculate,\
                                    0.6*self.maxKeyCardDuration)
        return d


class TestIcalBouncerCalSwitch(TestIcalBouncerRunning, RequiredModulesMixin):

    def _getCalendarFromString(self, data):
        tmp = tempfile.NamedTemporaryFile()
        tmp.write(data)
        tmp.flush()
        tmp.seek(0)
        return eventcalendar.fromFile(tmp)

    def testDonTRevoke(self):
        data = self.ical_from_specs('', self.now,
                                    '', self.in_half_an_hour)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        self.bouncer.authenticate(keycard)
        data = self.ical_from_specs('', self.a_day_ago,
                                    '', self.in_half_an_hour)

        calendar = self._getCalendarFromString(data)
        self.bouncer.get_main_algorithm().iCalScheduler.setCalendar(calendar)
        self.failUnless(self.bouncer.hasKeycard(keycard))

    def testRevoke(self):
        data = self.ical_from_specs('', self.now,
                                    '', self.in_half_an_hour)
        self.bouncer = self.bouncer_from_ical(data)

        keycard = keycards.KeycardGeneric()
        self.bouncer.authenticate(keycard)
        data = self.ical_from_specs('', self.a_day_ago,
                                    '', self.half_an_hour_ago)

        calendar = self._getCalendarFromString(data)
        self.bouncer.get_main_algorithm().iCalScheduler.setCalendar(calendar)
        self.failIf(self.bouncer.hasKeycard(keycard))
