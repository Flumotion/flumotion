# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# PYTHONPATH should be set so that if this is part of a Flumotion project,
# it points to misc so we can import setup.py from there
try:
    from misc import setup
    setup.setup()
except ImportError:
    print "Not importing misc.setup"
    pass

from flumotion.common import boot
boot.init_gobject()
boot.init_gst()
from twisted.internet import gtk2reactor
gtk2reactor.install(useGtk=False)

# reinstall our import hooks that could have been overridden by
# pygtk/pygst ltihooks
from flumotion.common import package
package.getPackager().install()

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

from twisted.internet.posixbase import PosixReactorBase


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
