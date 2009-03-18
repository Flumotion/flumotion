# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L. (www.fluendo.com).
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


import twisted


def haveTwisted(major, minor, micro=0):
    '''Check if we're running at least the given version of twisted.'''

    # looks like there is no better (fairly simple) way than check for
    # the stringified __version__ in the twisted module
    #
    # the following code should work with the current and the known
    # previous versions but forward compatibility is not guaranteed

    try:
        vtuple = twisted.__version__.split('.')
    except:
        # it's not a string? - it's not twisted!
        return False

    try:
        vconv = map(int, vtuple[:3])
    except ValueError, ve:
        # doesn't have at least 3 numerical components? - not a known twisted!
        return False

    return vconv >= [major, minor, micro]
