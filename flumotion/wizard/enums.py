# -*- Mode: Python; test-case-name: flumotion.test.test_enum -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/wizard/enums.py: python enum implementation
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




class EnumMetaClass(type):
    def __len__(self):
        return len(self.__enums__)

    def __getitem__(self, value):
        try:
            return self.__enums__[value]
        except KeyError:
            raise StopIteration

    def __setitem__(self, value, enum):
        self.__enums__[value] = enum
        setattr(self, enum.name, enum)


class Enum(object):
    __metaclass__ = EnumMetaClass
    def __init__(self, value, name, nick=None):
        self.value = value
        self.name = name
        
        if nick is None:
            nick = name
            
        self.nick = nick

    def __repr__(self):
        return '<enum %s of type %s>' % (self.name,
                                         self.__class__.__name__)

    def get(self, value):
        return self.__enums__[value]
    get = classmethod(get)

    def set(self, value, item):
        self[value] = item
    set = classmethod(set)


    
class EnumClass(object):
    def __new__(self, type_name, names=(), nicks=(), **extras):
        if nicks:
            if len(names) != len(nicks):
                raise TypeError("nicks must have the same length as names")
        else:
            nicks = names

        for extra in extras.values():
            if not isinstance(extra, tuple):
                raise TypeError('extra must be a tuple, not %s' % type(extra))
                
            if len(extra) != len(names):
                raise TypeError("extra items must have a length of %d" %
                                len(names))
            
        etype = EnumMetaClass(type_name, (Enum,), dict(__enums__={}))
        for value, name in enumerate(names):
            enum = etype(value, name, nicks[value])
            for extra_key, extra_values in extras.items():
                assert not hasattr(enum, extra_key)
                setattr(enum, extra_key, extra_values[value])
            etype[value] = enum
            
        return etype


# Sources
VideoDevice = EnumClass('VideoDevice',
                        ('Webcam', 'TVCard', 'Firewire', 'Test'),
                        ('Web camera',
                         'TV Card',
                         'Firewire video',
                         'Test video source'),
                        step=('Webcam',
                              'TV Card',
                              'Firewire',
                              'Test Source'),
                        component_type=('web-camera',
                                        'tv-card',
                                        'firewire-video',
                                        'videotest'))
AudioDevice = EnumClass('AudioDevice',
                        ('Soundcard', 'Firewire', 'Test'),
                        ('Sound card', 'Firewire Audio', 'Test audio source'),
                        component_type=('audiotest',
                                        'firewire-audio',
                                        'audiotest'))
# TVCard
TVCardDevice = EnumClass('TVCardDevice', ('/dev/video0',
                                          '/dev/video1',
                                          '/dev/video2'))
TVCardSignal = EnumClass('TVCardSignal', ('Composite', 'RCA'))

# Videotestsrc, order is important here, since it maps to
#               GstVideotestsrcPattern
VideoTestPattern = EnumClass('VideoTestPattern',
                             ('Bars', 'Snow', 'Black'),
                             ('SMPTE Color bars',
                              'Random (television snow)',
                              'Totaly black'))

VideoTestFormat = EnumClass('VideoTestFormat', ('YUV', 'RGB'))

# Sound card
SoundcardDevice = EnumClass('SoundcardDevice', ('/dev/dsp',
                                                '/dev/dsp1',
                                                '/dev/dsp2'))
SoundcardInput = EnumClass('SoundcardInput',
                           ('Line in', 'Microphone', 'CD'))
SoundcardChannels = EnumClass('SoundcardChannels', ('Stereo', 'Mono'))
SoundcardSamplerate = EnumClass('SoundcardSamplerate', ('44100',
                                                        '22050',
                                                        '11025',
                                                        '8000'))
SoundcardBitdepth = EnumClass('SoundcardBitdepth', ('16', '8'),
                              ('16-bit', '8-bit'))

# Encoding format
EncodingFormat = EnumClass('EncodingFormat', ('Ogg', 'Multipart'),
                           component_type=('ogg-muxer',
                                           'multipart-muxer'))
EncodingVideo = EnumClass('EncodingVideo',
                          ('Theora', 'Smoke', 'JPEG'),
                          component_type=('theora-encoder',
                                          'smoke-encoder',
                                          'jpeg-encoder'),
                          step=('Theora', 'Smoke', 'JPEG'))
EncodingAudio = EnumClass('EncodingAudio', ('Vorbis', 'Speex', 'Mulaw'),
                          component_type=('vorbis-encoder',
                                          'speex-encoder',
                                          'mulaw-encoder'),
                          step=('Vorbis', 'Speex', 'Mulaw'))

# Disk writer
RotateTime = EnumClass('RotateTime',
                       ('Minutes', 'Hours', 'Days', 'Weeks'),
                       ('minute(s)', 'hour(s)', 'day(s)', 'week(s)'),
                       unit=(60,
                              60*60,
                              60*60*24,
                              60*60*25*7))
RotateSize = EnumClass('RotateSize',
                      ('kB', 'MB', 'GB', 'TB'),
                       unit=(1 << 10L,
                              1 << 20L,
                              1 << 30L,
                              1 << 40L))
 
LicenseType = EnumClass('LicenseType',
                        ('CC', 'Commercial'),
                        ('Creative Commons', 'Commercial'))
