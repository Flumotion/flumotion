import sys
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

if __name__ == '__main__':
    import gstreactor
    gstreactor.install()

from twisted.internet import reactor
from twisted.python import log
from twisted.web import server, resource

from controller import ControllerServerFactory
from producer import Producer
from converter import Converter
from streamer import Streamer, StreamingResource

PRODUCER_PIPELINE = 'videotestsrc ! video/x-raw-yuv,width=320,height=240,framerate=5.0,format=(fourcc)I420'
PRODUCER2_PIPELINE = 'sinesrc'
CONVERTER_PIPELINE = '{ @producer1 ! ffmpegcolorspace ! theoraenc ! queue name=video } { @producer2 ! audioconvert ! rawvorbisenc ! queue name=audio } video.src ! oggmux name=muxer audio.src ! identity ! muxer. muxer.'
CONVERTER_PIPELINE_ = '@producer1 ! identity ! queue name=video } { @producer2 ! identity ! queue name=audio } video.src ! { oggmux name=muxer audio.src  ! muxer. muxer.'

controller_port = 8890
streaming_port = 8080

if __name__ == '__main__':
#    log.startLogging(sys.stdout)

    producer = Producer('producer1', [], PRODUCER_PIPELINE)
    producer2 = Producer('producer2', [], PRODUCER2_PIPELINE)
    converter = Converter('converter', ['producer1', 'producer2'], CONVERTER_PIPELINE)
    streamer = Streamer('streamer', ['converter'])
    
    reactor.listenTCP(controller_port, ControllerServerFactory())
    
    reactor.connectTCP('localhost', controller_port, producer.factory)
    reactor.connectTCP('localhost', controller_port, producer2.factory)
    reactor.connectTCP('localhost', controller_port, converter.factory)
    reactor.connectTCP('localhost', controller_port, streamer.factory)

    reactor.listenTCP(streaming_port, server.Site(resource=StreamingResource(streamer)))

    reactor.run()
