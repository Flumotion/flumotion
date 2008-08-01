# -*- Mode: Python; test-case-name: flumotion.test.test_pbstream -*-
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

import os

import gst
from twisted.spread import pb
from twisted.internet import reactor, defer
from twisted.cred import credentials
from twisted.cred import checkers, portal
from zope.interface import implements

from flumotion.common import log
from flumotion.common import testsuite




# this example sets up a PB connection from client to server,
# then steals the connection to do raw streaming instead
# this example also uses GStreamer to test if the streaming works at all

# general idea is like this:
# - PB Client has an eater/fdsrc
# - PB Server has a feeder/multifdsink
# - PB Client does callRemote('eatFrom'); response is ignored
# - PB Server in response does callRemote('feedTo')
# - PB Client remote_feedTo:
#   - stops reading from transport
#   - replies OK (ie return from the handler)
#   - waits for emptying of twisted send queue
#   - in a callLater(0), ie outside of the deferred, stops writing to transport
# - PB Server receives the result from callRemote('feedTo') and
#   starts streaming
# Client has an eater


class Client(pb.Referenceable, log.Loggable):
    """
    The Client has a GStreamer pipeline that uses an fdsrc to receive a GDP
    stream, decode it as Vorbis, and play it.
    The Client will request the Server to send it a stream over the PB
    transport fd.

    So it initiates the request by doing a remoteCall.
    The server will reply with a remoteCall of its own, and from that point on
    the transport fd will be used for raw streaming.
    """
    logCategory = "client"

    def __init__(self):
        self.debug("creating")
        self.pipeline = gst.parse_launch(
            "fdsrc name=src ! gdpdepay ! oggdemux ! vorbisdec"
            " ! fakesink name=sink signal-handoffs=TRUE")
        self.perspective = None
        self.src = self.pipeline.get_by_name('src')
        self.sink = self.pipeline.get_by_name('sink')
        self._id = self.sink.connect('handoff', self._handoff_cb)
        self.deferred = defer.Deferred() # fired when we receive a buffer

        srcpad = self.src.get_pad("src")
        srcpad.add_event_probe(self._probe_cb)

    def _probe_cb(self, pad, event):
        if event.type == gst.EVENT_EOS:
            self.debug('eos received, stopping')
            reactor.callFromThread(self.callback, "eos")

    def _handoff_cb(self, sink, buffer, pad):
        # called once, and only once
        self.debug("buffer received, stopping")
        sink.disconnect(self._id)
        self._id = None
        # we get executed from the streaming thread, so we want to
        # callback our deferred from the reactor thread
        reactor.callFromThread(self.callback, "handoff")

    def callback(self, reason):
        # fire our deferred
        if self.deferred:
            self.debug('firing callback because of %s' % reason)
            self.deferred.callback(None)
            self.deferred = None
        else:
            self.debug('deferred already fired, ignoring %s' % reason)

    def connected(self, perspective):
        self.debug("got perspective ref: %r" % perspective)
        self.perspective = perspective
        # import code; code.interact(local=locals())
        self.debug("CLIENT --> server: callRemote(eatFrom)")
        # this triggers the server to callRemote us
        d = perspective.callRemote("eatFrom")
        # we do not expect an answer from this callRemote - the other side
        # will not necessarily reply
        d.addCallback(self.eatFromCallback)

    def eatFromCallback(self, result):
        self.debug("CLIENT <-- server: callRemote(eatFrom): %r" % result)

    def remote_feedTo(self):
        self.debug("server --> CLIENT: remote_feedTo()")
        self.debug("doing stuff with transport")
        # transport is a twisted.internet.tcp.Client, so ultimately an
        # twisted.internet.abstract.FileDescriptor
        t = self.perspective.broker.transport
        self.debug("transport: %r" % t)
        #t.unregisterProducer()
        # exarkun says this is not public API
        # however, it has not changed since 1.3, and there is no public
        # API that achieves this
        self.debug("transport.stopReading()")
        t.stopReading() # this makes sure we don't receive PB messages anymore
        reactor.callLater(0, self._receiveStream, t)
        self.debug("server <-- CLIENT: remote_feedTo(): None")

    def _receiveStream(self, transport):
        # at this point dataBuffer should be empty, but there is still some
        # tempData
        self.debug("transport.dataBuffer: %r" % transport.dataBuffer)
        self.debug("transport._tempDataLen: %r" % transport._tempDataLen)
        self.debug("transport.doWrite()")
        # doWrite is called on the transport when there is data available to
        # write - we can use it as a way of flushing out the write queue
        ret = transport.doWrite()
        # None indicates a write, 0 indicates no write
        self.debug("transport.doWrite(): %r" % ret)
        assert ret == None

        # doWrite() should have written out everything else now, so both
        # should be 0
        self.debug("transport.dataBuffer: %r" % transport.dataBuffer)
        self.debug("transport._tempDataLen: %r" % transport._tempDataLen)
        self.debug("transport.stopWriting()")
        transport.stopWriting()
        fd = transport.fileno()
        self.debug("adding fd %d to fdsrc" % fd)
        # we store the transport, so that a ref to the socket is kept around
        # sneaky !
        self.transport = transport
        self.perspective.broker.transport = None
        self.src.set_property('fd', fd)
        self.pipeline.set_state(gst.STATE_PLAYING)

    def stop(self):
        self.pipeline.set_state(gst.STATE_NULL)
        # set the transport back for cleanup
        self.perspective.broker.transport = self.transport

# server has a feeder
class Server(log.Loggable):
    logCategory = "server"

    def __init__(self, immediateStop=False):
        # if immediateStop is True, the server will not actually hand off the
        # fd to multifdsink, but close it immediately
        self.pipeline = None
        self.client = None
        self.sink = None
        self.immediateStop = immediateStop

    def start(self):
        self.pipeline = gst.parse_launch(
            "audiotestsrc ! audioconvert ! vorbisenc ! "
            "oggmux ! gdppay ! multifdsink name=sink")
        self.sink = self.pipeline.get_by_name('sink')
        self.sink.connect('client-removed', self.client_removed_handler)
        self.pipeline.set_state(gst.STATE_PLAYING)

    def client_removed_handler(self, sink, fd, status):
        self.debug("client on fd %d removed, status %r" % (fd, status))

    def stop(self):
        self.pipeline.set_state(gst.STATE_NULL)

class Dispatcher(log.Loggable):
    logCategory = "dispatcher"
    implements(portal.IRealm)

    def __init__(self, server):
        self.debug("creating dispatcher")
        self.server = server

    def requestAvatar(self, avatarID, mind, *interfaces):
        self.debug("dispatcher: avatar being requested: %s" % avatarID)
        if avatarID == "admin":
            raise AssertionError
            # AdminAvatar(self.server)
        else:
            avatar = ClientAvatar(self.server)

        reactor.callLater(0, avatar.attached, mind)
        return (pb.IPerspective, avatar, avatar.detached)

class ClientAvatar(pb.Avatar, log.Loggable):
    logCategory = "clientavatar"
    # server-side object for client handling
    # if immediateStop, do not actually stream but try to shut down
    # the streaming immediately
    def __init__(self, server):
        self.server = server
        server.client = self
        self.transport = None

    def attached(self, mind):
        self.debug("ClientAvatar: mind %s attached" % mind)
        self.mind = mind

    def detached(self):
        self.debug("ClientAvatar: mind detached")
        pass

    def perspective_eatFrom(self):
        self.debug("client --> SERVER: perspective_eatFrom()")
        # a callLater makes the debug output slightly less confusing,
        # but a direct call works too
        #reactor.callLater(0, self.feedToClient)
        self.feedToClient()
        self.debug("client <-- SERVER: perspective_eatFrom(): None")

    def feedToClient(self):
        self.debug("SERVER --> client: callRemote(feedTo)")
        d = self.mind.callRemote('feedTo')
        d.addCallback(lambda r: self.startStreaming())

    def startStreaming(self):
        self.debug("SERVER <-- client: callRemote(feedTo): None")
        self.debug("startStreaming()")
        t = self.mind.broker.transport
        # exarkun says this is not public API
        # however, it has not changed since 1.3, and there is no public
        # API that achieves this
        self.debug("stopReading()")
        t.stopReading()
        self.debug("stopWriting()")
        t.stopWriting()
        fd = t.fileno()
        # we store the transport, so that a ref to the socket is kept around
        # sneaky !
        self.transport = t
        self.mind.broker.transport = None
        if self.server.immediateStop:
            self.debug('immediateStop, closing fd')
            os.close(fd)
        else:
            self.debug("adding fd %d to multifdsink" % fd)
            self.server.sink.emit('add', fd)

class TestClientEater(testsuite.TestCase):
    def startClient(self):
        factory = pb.PBClientFactory()
        factory.unsafeTracebacks = 1
        reactor.connectTCP("localhost", self.portno, factory)
        client = Client()
        d = factory.login(credentials.UsernamePassword("client", "pass"),
            client)
        d.addCallback(client.connected)
        self.clientFactory = factory

        return client

    def startServer(self, immediateStop=False):
        server = Server(immediateStop)
        server.start()
        p = portal.Portal(Dispatcher(server))
        p.registerChecker(checkers.InMemoryUsernamePasswordDatabaseDontUse(
            admin="pass", client="pass"))
        self.serverPort = reactor.listenTCP(0, pb.PBServerFactory(p))
        self.portno = self.serverPort.getHost().port

        return server

    def testRun(self):
        d = defer.Deferred()
        s = self.startServer()
        c = self.startClient()
        def stop(result):
            log.debug("main", "stop")
            gst.debug("main: stop")
            log.debug("main", "stop server")
            gst.debug("main: stop server")
            s.stop()
            log.debug("main", "stop client")
            gst.debug("main: stop client")
            c.stop()
            self.clientFactory.disconnect()
            self.serverPort.stopListening()
            log.debug("main", "stop test")
            # stop the test
            d.callback(None)
        c.deferred.addCallback(stop)
        return d

    def testRunImmediateStop(self):
        # this test shows that we can also stop the stream immediately
        # without handing off the fd to GStreamer
        d = defer.Deferred()
        s = self.startServer(immediateStop=True)
        c = self.startClient()
        def stop(result):
            log.debug("main", "stop")
            gst.debug("main: stop")
            log.debug("main", "stop server")
            gst.debug("main: stop server")
            s.stop()
            log.debug("main", "stop client")
            gst.debug("main: stop client")
            c.stop()
            self.clientFactory.disconnect()
            self.serverPort.stopListening()
            log.debug("main", "stop test")
            # stop the test
            d.callback(None)
        c.deferred.addCallback(stop)
        return d
