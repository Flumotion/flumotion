# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4


import pygtk
pygtk.require('2.0')

import gst
import gst.interfaces

# Install reactor, should move somewhere
from flumotion.twisted import gstreactor
gstreactor.install()

# Make sure config works
import flumotion.common.setup

# monkey patching twisted doc errors
from twisted.spread import pb
def login(self, credentials, client=None):
    """Login and get perspective from remote PB server.

    Currently only credentials implementing IUsernamePassword are
    supported.

    @return: Deferred of RemoteReference to the perspective."""
def getRootObject(self):
   """Get root object of remote PB server.

   @return: Deferred of the root object.
   """
def getPerspective(self, username, password, serviceName,
                       perspectiveName=None, client=None):
        """Get perspective from remote PB server.

        New systems should use login() instead.
        
        @return: Deferred of RemoteReference to the perspective.
        """

pb.PBClientFactory.login = login
pb.PBClientFactory.getRootObject = getRootObject 
pb.PBClientFactory.getPerspective = getPerspective

from twisted.internet.default import PosixReactorBase

def listenUDP(self, port, protocol, interface='', maxPacketSize=8192):
    """Connects a given DatagramProtocol to the given numeric UDP port.
	
    EXPERIMENTAL.

    @returns: object conforming to IListeningPort.
    """

def connectUDP(self, remotehost, remoteport, protocol, localport=0,
	       interface='', maxPacketSize=8192):
    """Connects a ConnectedDatagramProtocol instance to a UDP port.
    
    EXPERIMENTAL.
    """

PosixReactorBase.listenUDP = listenUDP
PosixReactorBase.listenUNIXDatagram = listenUDP
PosixReactorBase.connectUDP = connectUDP
PosixReactorBase.connectUNIXDatagram = connectUDP

from epydoc.cli import cli
cli()
