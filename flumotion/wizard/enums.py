# -*- Mode: Python; test-case-name: flumotion.test.test_enum -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/launcher.py: launch grids
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
    def __getitem__(self, value):
        try:
            return self.__enums__[value]
        except KeyError:
            raise StopIteration


class Enum(object):
    __metaclass__ = EnumMetaClass
    def __init__(self, value, name, nick):
        self.value = value
        self.name = name
        self.nick = nick

    def __repr__(self):
        return '<enum %s of type %s>' % (self.name,
                                         self.__class__.__name__)
    
    def get(self, value):
        return self.__enums__[value]
    get = classmethod(get)

    
    
class EnumClass(object):
    def __new__(self, name, values=(), values_repr=()):
        if values_repr:
            if len(values) != len(values_repr):
                raise TypeError("values_repr must be same length as value")
        else:
            values_repr = values

        enums = {}
        enum_type = EnumMetaClass(name, (Enum,),
                                  dict(__enums__=enums))
        for value, name in enumerate(values):
            nick = values_repr[value]
            enum = enum_type(value, name, nick)
            enums[value] = enum
            setattr(enum_type, name, enum)
        return enum_type


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
SoundcardBitdepth = EnumClass('SoundcardBitdepth', ('16', '8'))

# Encoding format
EncodingFormat = EnumClass('EncodingFormat', ('Ogg', 'Multipart'))
EncodingVideo = EnumClass('EncodingVideo', ('Theora', 'Smoke', 'JPEG'))
EncodingAudio = EnumClass('EncodingAudio', ('Vorbis', 'Speex', 'Mulaw'))

# Disk writer
RotateTime = EnumClass('RotateTime',
                      ('minutes', 'hours', 'days', 'weeks', 'months'))
RotateSize = EnumClass('RotateSize',
                      ('kB', 'MB', 'GB', 'TB'))
 
