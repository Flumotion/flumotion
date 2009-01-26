# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
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

"""convert to and from fractions
"""

__version__ = "$Rev$"

import math


def gcd(a, b):
    """
    Returns the greatest common divisor of two integers.

    @type a: int
    @type b: int

    @rtype : int
    """
    while b:
        a, b = b, a % b

    return a


def fractionFromValue(value):
    """
    Converts a value to a fraction

    @param value: the value to convert to a tuple
    @type  value: one of
      - string, unicode
      - number, eg int/float/long
      - two sized tuple

    @returns: the fraction
    @rtype:   a two sized tuple with 2 integers
    """

    def _frac(num, denom=1):
        return int(num), int(denom)

    if isinstance(value, basestring):
        noSlashes = value.count('/')
        if noSlashes == 0:
            parts = [value]
        elif noSlashes == 1:
            parts = value.split('/')
        else:
            raise ValueError('Expected at most one /, not %r' % (value, ))
        return _frac(*parts)
    elif isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError(
                "Can only convert two sized tuple to fraction")
        return value
    elif isinstance(value, (int, long)):
        return _frac(value)
    elif isinstance(value, float):
        ipart = int(value)
        fpart = value - ipart

        if not fpart:
            return _frac(value)
        else:
            den = math.pow(10, len(str(fpart))-2)
            num = value*den
            div = gcd(num, den)
            return _frac(num/div, den/div)
    else:
        raise ValueError(
            "Cannot convert %r of type %s to a fraction" % (
            value, type(value).__name__))


def fractionAsFloat(value):
    """
    Converts a fraction to a float
    @param value: the value to convert to a tuple, can be one of:
    @type value: a two sized tuple with 2 integers
    @returns: fraction representation in float
    @rtype: float
    """
    assert type(value) in [list, tuple], value
    assert len(value) == 2, value
    return float(value[0]) / float(value[1])


def fractionAsString(value):
    """
    Converts a fraction to a string
    @param value: the value to convert to a tuple, can be one of:
    @type value: a two sized tuple with 2 integers
    @returns: fraction representation as a string
    @rtype: string
    """
    assert type(value) in [list, tuple], value
    assert len(value) == 2, value
    return '%s/%s' % value
