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
    def __new__(self, type_name, names=(), nicks=()):
        if nicks:
            if len(names) != len(nicks):
                raise TypeError("nicks must have the same length as names")
        else:
            nicks = names

        etype = EnumMetaClass(type_name, (Enum,), dict(__enums__={}))
        for value, name in enumerate(names):
            etype[value] = etype(value, name, nicks[value])
            
        return etype


# Sources
VideoDevice = EnumClass('VideoDevice',
                        ('TVCard', 'Firewire', 'Webcam', 'Test'),
                        ('TV Card',
                         'Firewire video',
                         'Web camera',
                         'Test video source'))
AudioDevice = EnumClass('AudioDevice',
                        ('Firewire', 'Soundcard', 'Test'),
                        ('Firewire Audio', 'Sound card',
                         'Test audio source'))
# TVCard
TVCardDevice = EnumClass('TVCardDevice', ('/dev/video0',
                                          '/dev/video1',
                                          '/dev/video2'))
TVCardSignal = EnumClass('TVCardSignal', ('Composite', 'RCA'))

# Videotestsrc
VideoTestPattern = EnumClass('VideoTestPattern', ('Bars', 'Snow',
                                                  'Black'))
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
EncodingFormat = EnumClass('EncodingFormat', ('Ogg', 'Multipart'))
EncodingVideo = EnumClass('EncodingVideo', ('Theora', 'Smoke', 'JPEG'))
EncodingAudio = EnumClass('EncodingAudio', ('Vorbis', 'Speex', 'Mulaw'))

# Disk writer
RotateTime = EnumClass('RotateTime',
                       ('Minutes', 'Hours', 'Days', 'Weeks', 'Months'),
                       ('minute(s)', 'hour(s)', 'day(s)', 'week(s)', 'month(s)'))
RotateSize = EnumClass('RotateSize',
                      ('kB', 'MB', 'GB', 'TB'))
 
