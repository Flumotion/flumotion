# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# common.py: common functionality
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

"""
A set of common functions.
"""

def formatStorage(units, precision = 2):
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

    prefixes = ['E', 'P', 'T', 'G', 'M', 'k', '']

    value = float(units)
    prefix = prefixes.pop()
    while prefixes and value >= 1000:
        prefix = prefixes.pop()
        value /= 1000

    format = "%%.%df %%s" % precision
    return format % (value, prefix)

def formatTime(seconds):
    """
    Nicely format time in a human-readable format.
    Will chunks weeks, days, hours and minutes.

    @param seconds: the time in seconds to format.
    @type  seconds: int or float

    @rtype: string
    @returns: a nicely formatted time string.
    """
    chunks = []
    
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

    if weeks > 1:
        chunks.append('%d weeks' % weeks)
    elif weeks == 1:
        chunks.append('1 week')

    if days > 1:
        chunks.append('%d days' % days)
    elif days == 1:
        chunks.append('1 day')

    chunks.append('%02d:%02d' % (hours, minutes))

    return " ".join(chunks)
