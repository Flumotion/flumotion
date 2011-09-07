# -*- Mode:Python; test-case-name:flumotion.test.test_common_eventcalendar -*-
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

import datetime
import time

HAS_DATEUTIL = False
try:
    from dateutil import tz
    HAS_DATEUTIL = True
except ImportError:
    pass


def gettz(tzid):
    """
    Gets the right timezone from the environment or the given string
    """
    if not HAS_DATEUTIL:
        return None
    return tz.gettz(tzid)


class DSTTimezone(datetime.tzinfo):
    """ A tzinfo class representing a DST timezone """

    ZERO = datetime.timedelta(0)

    def __init__(self, tzid, stdname, dstname, stdoffset, dstoffset,
                 stdoffsetfrom, dstoffsetfrom, dststart, dstend,
                 stdrrule, dstrrule):
        '''
        @param tzid:            Timezone unique ID
        @type  tzid:            str
        @param stdname:         Name of the Standard observance
        @type  stdname:         str
        @param dstname:         Name of the DST observance
        @type  dstname:         str
        @param stdoffset:       UTC offset for the standard observance
        @type  stdoffset:       L{datetime.timedelta}
        @param dstoffset:       UTC offset for the DST observance
        @type  dstoffset:       L{datetime.timedelta}
        @param stdoffsetfrom:   UTC offset which is in use when the onset of
                                Standard observance begins
        @type  stdoffsetfrom:   l{datetime.timedelta}
        @param dstoffsetfrom:   UTC offset which is in use when the onset of
                                DST observance begins
        @type  stdoffsetfrom:   L{datetime.timedelta}
        @param dststart:        Start of the DST observance
        @type  dststart:        L{datetime.datetime}
        @param dstend:          End of the DST observance
        @type  dstend:          L{datetime.datetime}
        @param stdrrule:        Recurrence rule for the standard observance
        @type  stdrrule:        L{rrule.rrule}
        @param dstrrule:        Recurrence rule for the daylight observance
        @type  dstrrule:        L{rrule.rrule}
        '''

        self._tzid = str(tzid)
        self._stdname = str(stdname)
        self._dstname = str(dstname)
        self._stdoffset = stdoffset
        self._dstoffset = dstoffset
        self._stdoffsetfrom = stdoffsetfrom
        self._dstoffsetfrom = dstoffsetfrom
        self._dststart = dststart
        self._dstend = dstend
        self._stdrrule = stdrrule
        self._dstrrule = dstrrule

    def __str__(self):
        return self._tzid

    def tzname(self, dt):
        return self._isdst(dt) and self._dstname or self._stdname

    def utcoffset(self, dt):
        return self._isdst(dt) and self._dstoffset or self._stdoffset

    def fromutc(self, dt):
        dt = dt.replace(tzinfo=None)
        return self._isdst(dt) and \
                dt + self._dstoffsetfrom or dt + self._stdoffsetfrom

    def dst(self, dt):
        if dt is None or dt.tzinfo is None:
            return self.ZERO
        assert dt.tzinfo is self
        return self._isdst(dt) and self._dstoffset - self._stdoffset or \
                self.ZERO

    def copy(self):
        # The substraction is done converting the datetime values to UTC and
        # adding the utcoffset of each one (see 9.1.4 datetime Objects)
        # which is done only if both datetime are 'aware' and have different
        # tzinfo member, that's why we need a way to copy an instance
        return DSTTimezone(self._tzid, self._stdname, self._dstname,
                self._stdoffset, self._dstoffset, self._stdoffsetfrom,
                self._dstoffsetfrom, self._dststart, self._dstend,
                self._stdrrule, self._dstrrule)

    def _isdst(self, dt):
        if self._dstoffset is None or dt.year < self._dststart.year:
            return False
        firstDayOfYear = datetime.datetime(dt.year, 1, 1)
        start = self._dstrrule.after(firstDayOfYear, True)
        end = self._stdrrule.after(firstDayOfYear)
        return start <= dt.replace(tzinfo=None) < end


class FixedOffsetTimezone(datetime.tzinfo):
    """Fixed offset in hours from UTC."""

    def __init__(self, offset, name):
        self.__offset = offset
        self.__name = name

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self, dt):
        return datetime.timedelta(0)

    def copy(self):
        return FixedOffsetTimezone(self.__offset, self.__name)


class LocalTimezone(datetime.tzinfo):
    """A tzinfo class representing the system's idea of the local timezone"""

    EPOCHORDINAL = datetime.datetime.utcfromtimestamp(0).toordinal()
    ZERO = datetime.timedelta(0)

    def __init__(self, *args):
        datetime.tzinfo.__init__(self, args)
        self._std_offset = datetime.timedelta(seconds=-time.timezone)
        if time.daylight:
            self._dst_offset = datetime.timedelta(seconds=-time.altzone)
        else:
            self._dst_offset = self._std_offset
        self._dst_diff = self._dst_offset - self._std_offset

    def utcoffset(self, dt):
        if self._isdst(dt):
            return self._dst_offset
        else:
            return self._std_offset

    def dst(self, dt):
        if self._isdst(dt):
            return self._dst_diff
        else:
            return self.ZERO

    def tzname(self, dt):
        return time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        timestamp = ((dt.toordinal() - self.EPOCHORDINAL) * 86400
                     + dt.hour * 3600
                     + dt.minute * 60
                     + dt.second)
        return time.localtime(timestamp+time.timezone).tm_isdst
LOCAL = LocalTimezone()


class UTCTimezone(datetime.tzinfo):
    """A tzinfo class representing UTC"""
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO
UTC = UTCTimezone()
