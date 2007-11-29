# -*- Mode: Python; test-case-name: flumotion.test.test_enum -*-
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

"""
I contain a set of enums used in UI's for Flumotion.
"""

from gettext import gettext as _
from flumotion.common import enum

#
# Sources
#

VideoDevice = enum.EnumClass(
    'VideoDevice',
    ['Test', 'Webcam', 'TVCard', 'Firewire'],
    [_('Test video source'),
     _('Web camera'),
     _('TV card'),
     _('Firewire video'),
     ],
    step=['Test Video Source',
          'Webcam',
          'TV Card',
          'Firewire'
          ],
    component_type=[
        'videotest-producer',
        'webcam-producer',
        'tvcard-producer',
        'firewire-producer'
        ],
    element_names=[
        ['videotestsrc'],
        ['v4lsrc'],
        ['v4lsrc'],
        ['dvdec', 'gst1394src'],
        ])

AudioDevice = enum.EnumClass(
    'AudioDevice',
    ['Test', 'Soundcard', 'Firewire'],
    [_('Test audio source'),
     _('Sound card'),
     _('Firewire audio'),
     ],
    step=['Test Audio Source',
          'Soundcard',
          'Firewire audio',
          ],
    component_type=[
        'audiotest-producer',
        'soundcard-producer',
        'firewire-producer'
        ])

#
# TVCard
#

TVCardDevice = enum.EnumClass(
    'TVCardDevice',
    ['/dev/video0',
     '/dev/video1',
     '/dev/video2'])

TVCardSignal = enum.EnumClass(
    'TVCardSignal',
    ['Composite', 'RCA'],
    [_('Composite'), _('RCA')])


#
# Videotestsrc, order is important here, since it maps to
#               GstVideotestsrcPattern
#
VideoTestPattern = enum.EnumClass(
    'VideoTestPattern',
    ['Bars', 'Snow', 'Black'],
    [_('SMPTE Color bars'),
     _('Random (television snow)'),
     _('Totally black')])

VideoTestFormat = enum.EnumClass(
    'VideoTestFormat',
    ['YUV', 'RGB'],
    [_('YUV'), _('RGB')])

AudioTestSamplerate = enum.EnumClass(
    'AudioTestSamplerate',
    ['8000',
     '16000',
     '32000',
     '44100'])

#
# Sound card
#

SoundcardSystem = enum.EnumClass(
    'SoundcardSystem',
    ['Alsa', 'OSS'],
    element_name=['alsasrc', 'osssrc'])

#
# Encoding format
#

EncodingFormat = enum.EnumClass(
    'EncodingFormat',
    ['Ogg', 'Multipart'],
    [_('Ogg'), _('Multipart')],
    component_type=('ogg-muxer',
                    'multipart-muxer'))

EncodingVideo = enum.EnumClass(
    'EncodingVideo',
    ['Theora', 'Smoke', 'JPEG'],
    step=['Theora encoder', 'Smoke encoder',
          'JPEG encoder'],
    component_type=['theora-encoder',
                    'smoke-encoder',
                    'jpeg-encoder'])
EncodingAudio = enum.EnumClass(
    'EncodingAudio',
    ['Vorbis', 'Speex', 'Mulaw'],
    step=['Vorbis encoder', 'Speex encoder',
          'Mulaw encoder'],
    component_type=['vorbis-encoder',
                    'speex-encoder',
                    'mulaw-encoder'])

#
# Disk writer
#

RotateTime = enum.EnumClass(
    'RotateTime',
    ['Minutes', 'Hours', 'Days', 'Weeks'],
    [_('minute(s)'),
     _('hour(s)'),
     _('day(s)'),
     _('week(s)')],
    unit=(60,
          60*60,
          60*60*24,
          60*60*25*7))
RotateSize = enum.EnumClass(
    'RotateSize',
    ['kB', 'MB', 'GB', 'TB'],
    [_('kB'), _('MB'), _('GB'), _('TB')],
    unit=(1 << 10L,
          1 << 20L,
          1 << 30L,
          1 << 40L))

LicenseType = enum.EnumClass(
    'LicenseType',
    ['CC', 'Commercial'],
    [_('Creative Commons'),
     _('Commercial')])
