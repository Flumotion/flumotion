# -*- Mode: Python; test-case-name: flumotion.test.test_enum -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/wizard/enums.py: python enum implementation
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from flumotion.common import enum

# Sources
VideoDevice = enum.EnumClass('VideoDevice',
                        ('Webcam', 'TVCard', 'Firewire', 'Test'),
                        ('Web camera',
                         'TV card',
                         'Firewire video',
                         'Test video source'),
                        step=('Webcam',
                              'TV Card',
                              'Firewire',
                              'Test Video Source'),
                        component_type=('web-camera',
                                        'tv-card',
                                        'firewire',
                                        'videotest'),
                        element_names=(('v4lsrc',),
                                       ('v4lsrc',),
                                       ('videotestsrc',),
                                       ('dvdec', 'gst1394src')))
AudioDevice = enum.EnumClass('AudioDevice',
                        ('Soundcard', 'Firewire', 'Test'),
                        ('Sound card', 'Firewire audio', 'Test audio source'),
                        step=('Soundcard', 'Unused', 'Test Audio Source'),
                        component_type=('soundcard',
                                        'firewire',
                                        'audiotest'))
# TVCard
TVCardDevice = enum.EnumClass('TVCardDevice', ('/dev/video0',
                                          '/dev/video1',
                                          '/dev/video2'))
TVCardSignal = enum.EnumClass('TVCardSignal', ('Composite', 'RCA'))

# Videotestsrc, order is important here, since it maps to
#               GstVideotestsrcPattern
VideoTestPattern = enum.EnumClass('VideoTestPattern',
                             ('Bars', 'Snow', 'Black'),
                             ('SMPTE Color bars',
                              'Random (television snow)',
                              'Totally black'))

VideoTestFormat = enum.EnumClass('VideoTestFormat', ('YUV', 'RGB'))

AudioTestSamplerate = enum.EnumClass('AudioTestSamplerate', ('8000',
                                                        '16000',
                                                        '32000',
                                                        '44100'))

# Sound card
SoundcardSystem = enum.EnumClass('SoundcardSystem', ('OSS',
                                                'Alsa'),
                            element=('osssrc', 'alsasrc'))

SoundcardOSSDevice = enum.EnumClass('SoundcardOSSDevice', ('/dev/dsp',
                                                      '/dev/dsp1',
                                                      '/dev/dsp2'))
SoundcardAlsaDevice = enum.EnumClass('SoundcardAlsaDevice', ('hw:0',
                                                        'hw:1',
                                                        'hw:2'))
SoundcardInput = enum.EnumClass('SoundcardInput',
                           ('Line in', 'Microphone', 'CD'))
SoundcardChannels = enum.EnumClass('SoundcardChannels', ('Stereo', 'Mono'),
                              intvalue=(2, 1))
SoundcardSamplerate = enum.EnumClass('SoundcardSamplerate', ('44100',
                                                        '22050',
                                                        '11025',
                                                        '8000'))
SoundcardBitdepth = enum.EnumClass('SoundcardBitdepth', ('16', '8'),
                              ('16-bit', '8-bit'))

# Encoding format
EncodingFormat = enum.EnumClass('EncodingFormat', ('Ogg', 'Multipart'),
                           component_type=('ogg-muxer',
                                           'multipart-muxer'))
EncodingVideo = enum.EnumClass('EncodingVideo',
                          ('Theora', 'Smoke', 'JPEG'),
                          component_type=('theora-encoder',
                                          'smoke-encoder',
                                          'jpeg-encoder'),
                          step=('Theora', 'Smoke', 'JPEG'))
EncodingAudio = enum.EnumClass('EncodingAudio', ('Vorbis', 'Speex', 'Mulaw'),
                          component_type=('vorbis-encoder',
                                          'speex-encoder',
                                          'mulaw-encoder'),
                          step=('Vorbis', 'Speex', 'Mulaw'))

# Disk writer
RotateTime = enum.EnumClass('RotateTime',
                       ('Minutes', 'Hours', 'Days', 'Weeks'),
                       ('minute(s)', 'hour(s)', 'day(s)', 'week(s)'),
                       unit=(60,
                              60*60,
                              60*60*24,
                              60*60*25*7))
RotateSize = enum.EnumClass('RotateSize',
                      ('kB', 'MB', 'GB', 'TB'),
                       unit=(1 << 10L,
                              1 << 20L,
                              1 << 30L,
                              1 << 40L))
 
LicenseType = enum.EnumClass('LicenseType',
                        ('CC', 'Commercial'),
                        ('Creative Commons', 'Commercial'))
