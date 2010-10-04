# -*- Mode: Python; test-case-name: flumotion.test.test_common_format -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""formatting functions for storage, time, etc
"""

import gettext
import locale
import sys
import time

from flumotion.common.i18n import N_
from flumotion.configure import configure

_ = gettext.gettext
__version__ = "$Rev$"


def formatStorage(units, precision=2):
    """
    Nicely formats a storage size using SI units.
    See Wikipedia and other sources for rationale.
    Prefixes are k, M, G, ...
    Sizes are powers of 10.
    Actual result should be suffixed with bit or byte, not b or B.

    @param units:     the unit size to format
    @type  units:     int or float
    @param precision: the number of floating point digits to use
    @type  precision: int

    @rtype: string
    @returns: value of units, formatted using SI scale and the given precision
    """

    # XXX: We might end up calling float(), which breaks
    #      when using LC_NUMERIC when it is not C -- only in python
    #      2.3 though, no prob in 2.4. See PEP 331
    if sys.version_info < (2, 4):
        locale.setlocale(locale.LC_NUMERIC, "C")

    prefixes = ['E', 'P', 'T', 'G', 'M', 'k', '']

    value = float(units)
    prefix = prefixes.pop()
    while prefixes and value >= 1000:
        prefix = prefixes.pop()
        value /= 1000

    format = "%%.%df %%s" % precision
    return format % (value, prefix)


def formatTime(seconds, fractional=0):
    """
    Nicely format time in a human-readable format, like
    5 days 3 weeks HH:MM

    If fractional is zero, no seconds will be shown.
    If it is greater than 0, we will show seconds and fractions of seconds.
    As a side consequence, there is no way to show seconds without fractions)

    @param seconds:    the time in seconds to format.
    @type  seconds:    int or float
    @param fractional: how many digits to show for the fractional part of
                       seconds.
    @type  fractional: int

    @rtype: string
    @returns: a nicely formatted time string.
    """
    chunks = []

    if seconds < 0:
        chunks.append(('-'))
        seconds = -seconds

    week = 60 * 60 * 24 * 7
    weeks = seconds / week
    seconds %= week

    day = 60 * 60 * 24
    days = seconds / day
    seconds %= day

    hour = 60 * 60
    hours = seconds / hour
    seconds %= hour

    minute = 60
    minutes = seconds / minute
    seconds %= minute

    if weeks >= 1:
        chunks.append(gettext.dngettext(
            configure.PACKAGE,
            N_('%d week'), N_('%d weeks'), weeks) % weeks)
    if days >= 1:
        chunks.append(gettext.dngettext(
            configure.PACKAGE,
            N_('%d day'), N_('%d days'), days) % days)

    chunk = _('%02d:%02d') % (hours, minutes)
    if fractional > 0:
        chunk += ':%0*.*f' % (fractional + 3, fractional, seconds)

    chunks.append(chunk)

    return " ".join(chunks)


def formatTimeStamp(timeOrTuple):
    """
    Format a timestamp in a human-readable format.

    @param timeOrTuple: the timestamp to format
    @type  timeOrTuple: something that time.strftime will accept

    @rtype: string
    @returns: a nicely formatted timestamp string.
    """
    return time.strftime("%Y-%m-%d %H:%M %Z", timeOrTuple)


def strftime(format, t):
    """A version of time.strftime that can handle unicode formats.
    @param format: format to convert, see man strftime(3)
    @param t: time tuple as returned by time.localtime()
    """
    out = []
    percent = False
    for c in format:
        if percent:
            out.append(time.strftime('%' + c, t))
            percent = False
        elif c == '%':
            percent = True
        else:
            out.append(c)
    if percent:
        out.append('%')
    return ''.join(out)
