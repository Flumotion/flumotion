# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/common.py: common functionality
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

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

def version(binary):
    """
    Print a version block for the flumotion binaries.

    @arg binary: name of the binary
    @type binary: string
    """
    from flumotion.configure import configure

    block = []
    block.append("%s %s" % (binary, configure.version))
    block.append("part of Flumotion - a streaming media server")
    block.append("(C) Copyright 2004 Fluendo")
    return "\n".join(block)
             
def mergeImplements(*classes):
    """
    Merge the __implements__ tuples of the given classes into one tuple.
    """
    allYourBase = []
    for clazz in classes:
        allYourBase += getattr(clazz, '__implements__', ())
    return tuple(allYourBase)

