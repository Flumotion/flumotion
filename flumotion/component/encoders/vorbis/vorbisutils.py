# -*- Mode: Python -*-
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

__version__ = "$Rev$"


def get_preferred_sample_rate(maxrate):
    """ Get the preferred 'standard' sample rate not exceeded maxrate"""
    rates = [192000, 96000, 48000, 44100, 32000, 34000, 22050, 16000, 12000,
             11025, 8000]

    for rate in rates:
        if rate <= maxrate:
            return rate

    return 8000


def get_max_sample_rate(bitrate, channels):
    # maybe better in a hashtable/associative array?
    # ZAHEER: these really are "magic" limits that i found by trial and
    # error used
    # by libvorbis's encoder to determine what maximum samplerate it
    # accepts for a bitrate, numchannels combo
    # THOMAS: strangely enough they don't seem to be easily extractable from
    # vorbis/lib/modes/setup_*.h
    # might make sense to figure this out once and for all and verify
    # GStreamer's behaviour as well
    if channels == 2:
        if bitrate >= 45000:
            retval = 50000
        elif bitrate >= 40000:
            retval = 40000
        elif bitrate >= 30000:
            retval = 26000
        elif bitrate >= 24000:
            retval = 19000
        elif bitrate >= 16000:
            retval = 15000
        elif bitrate >= 12000:
            retval = 9000
        else:
            retval = -1

    elif channels == 1:
        if bitrate >= 32000:
            retval = 50000
        elif bitrate >= 24000:
            retval = 40000
        elif bitrate >= 16000:
            retval = 26000
        elif bitrate >= 12000:
            retval = 15000
        elif bitrate >= 8000:
            retval = 9000
        else:
            retval = -1

    return retval
