class Enum:
    def __init__(self, name, values=[]):
        self.name = name
        self.next = 0

        self._values = {}
        for value in values:
            if type(value) == tuple:
                if len(value) != 2:
                    raise TypeError, 'must be a length of 2'
                name = value[0]
                value = value[1]
            elif type(value) == str:
                name = value
                value = self.next
                self.next += 1
            else:
                raise TypeError
            
            assert not hasattr(self, name)
            assert not self._values.has_key(name)
            setattr(self, name, value)
            self._values[value] = name

    def __len__(self):
        return len(self._values)
    
    def __getitem__(self, item):
        try:
            name = self.get(item)
        except KeyError:
            raise StopIteration
        return getattr(self, name), name
        
    def get(self, value):
        return self._values[value]


VideoDeviceType = Enum('VideoDeviceType',
                       ('TVCard', 'Firewire', 'Webcam', 'Test'))
AudioDeviceType = Enum('AudioDeviceType',
                       ('Firewire', 'Sound card', 'Test'))
EncodingFormat = Enum('EncodingFormat', ('Ogg', 'Multipart'))
EncodingVideo = Enum('EncodingVideo', ('Theora', 'Smoke', 'JPEG'))
EncodingAudio = Enum('EncodingAudio', ('Vorbis', 'Speex', 'Mulaw'))
RotateTimeType = Enum('RotateTimeType',
                      ('minutes', 'hours', 'days', 'weeks', 'months'))
RotateSizeType = Enum('RotateSizeType',
                      ('kB', 'MB', 'GB', 'TB'))

TVCardDeviceType = Enum('TVCardDeviceType', ('/dev/video0',
                                             '/dev/video1',
                                             '/dev/video2'))
TVCardSignalType = Enum('TVCardSignalType', ('Composite', 'RCA'))
VideoTestPatternType = Enum('VideoTestPatternType', ('Bars', 'Snow', 'Black'))
VideoTestFormatType = Enum('VideoTestFormatType', ('YUV', 'RGB'))
