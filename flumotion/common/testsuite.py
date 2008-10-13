# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""testsuite base classes and helpers for diffing strings
"""

import twisted.copyright
from twisted.spread import pb
from twisted.internet import reactor, defer, selectreactor
from twisted.trial import unittest

from flumotion.common import log
from flumotion.configure import configure

__version__ = "$Rev$"


class BaseTestCase(unittest.TestCase, log.Loggable):

    # A sequence of reactors classes that this test supports, can be
    # overridden in subclasses. You can also set this to an empty
    # sequence, which means "any reactor"
    supportedReactors = [selectreactor.SelectReactor]

    # TestCase in Twisted 2.0 doesn't define failUnlessFailure method.
    if not hasattr(unittest.TestCase, 'failUnlessFailure'):

        def failUnlessFailure(self, deferred, *expectedFailures):

            def _cb(result):
                self.fail("did not catch an error, instead got %r" %
                          (result, ))

            def _eb(failure):
                failure.trap(*expectedFailures)
                return failure.value
            return deferred.addCallbacks(_cb, _eb)
        assertFailure = failUnlessFailure

    def __init__(self, methodName='runTest'):
        # skip the test if the class specifies supportedReactors and
        # the current reactor is not among them
        self.maybe_skip()
        unittest.TestCase.__init__(self, methodName)

    def maybe_skip(self):
        if (self.supportedReactors and
            type(reactor) not in self.supportedReactors):
            self.skip = "this test case does not support " \
                "running with %s as the reactor" % reactor

    # Loggable and TestCase both have a debug method; prefer ours

    def debug(self, *args, **kwargs):
        log.Loggable.debug(self, *args, **kwargs)


# Twisted changed the TestCase.__init__ signature several
# times.
#
# In versions older than 2.1.0 there was no __init__ method.
#
# In versions 2.1.0 up to 2.4.0 there is a __init__ method
# with a methodName kwarg that has a default value of None.
#
# In version 2.5.0 the default value of the kwarg was changed
# to "runTest".
#
# In versions above 2.5.0 God only knows what's the default
# value, as we do not currently support them.
twisted_version = tuple(map(int, twisted.copyright.version.split('.')))

if twisted_version < (2, 1, 0):

    class TestCase(BaseTestCase):

        def __init__(self):
            self.maybe_skip()
            unittest.TestCase.__init__(self)
elif twisted_version < (2, 5, 0):

    class TestCase(BaseTestCase):

        def __init__(self, methodName=None):
            BaseTestCase.__init__(self, methodName)
else:

    class TestCase(BaseTestCase):
        pass

# test objects to be used in unittests to simulate the processes
# subclass them to add your own methods


class TestClient(pb.Referenceable):

    type = "client" # override in subclass
    remoteRoot = None # RemoteReference to the server-side root

    def run(self, port):
        """
        Start the client by connecting to the server on the given port.

        @type port: int

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self._f = pb.PBClientFactory()
        self._p = reactor.connectTCP("127.0.0.1", port, self._f)
        d = self._f.getRootObject()
        d.addCallback(self._gotRootObject)
        return d

    def stop(self):
        """
        Stop the client.

        @rtype: L{twisted.internet.defer.Deferred}
        """
        self._p.disconnect()
        return self._dDisconnect

    def _gotRootObject(self, remoteReference):
        self.remoteRoot = remoteReference

        # make sure we will get a deferred fired on disconnect
        # so that the broker gets cleaned up from the reactor as well
        self._dDisconnect = defer.Deferred()
        self.remoteRoot.notifyOnDisconnect(
            lambda r: self._dDisconnect.callback(None))
        return self.remoteRoot.callRemote('identify', self.type, self)

    def remote_receive(self, object):
        # called by the server to send us an object
        self.object = object


class TestAdmin(TestClient):
    type = 'admin'


class TestWorker(TestClient):
    type = 'worker'


class TestManagerRoot(pb.Root, log.Loggable):
    logCategory = "testmanagerroot"

    def remote_identify(self, who, reference):
        """
        Called by a TestClient to announce the type of client, and give
        a reference.
        """
        self.debug('remote_identify: who %r, ref %r' % (who, reference))
        key = who + 'Reference'
        setattr(self, key, reference)

    def remote_receive(self, object):
        # called by the client to send us an object
        self.object = object


class TestManager:

    def run(self, rootClass):
        """
        Run the test manager.  Return port it is listening on.

        @type  rootClass: subclass of L{TestManagerRoot}

        @rtype: int
        """
        self.root = rootClass()
        factory = pb.PBServerFactory(self.root)
        factory.unsafeTracebacks = 1
        self._p = reactor.listenTCP(0, factory, interface="127.0.0.1")
        port = self._p.getHost().port
        return port

    def stop(self):
        """
        Stop the server.
        """
        return self._p.stopListening()


class TestPB(log.Loggable):
    """
    I combine a manager and a client to test passing back and forth objects.
    """
    logCategory = "testpb"

    def __init__(self):
        self.manager = TestManager()
        self.client = TestClient()

    def start(self):
        port = self.manager.run(TestManagerRoot)
        return self.client.run(port)

    def stop(self):
        d = self.manager.stop()
        d.addCallback(lambda r: self.client.stop())
        return d

    def send(self, object):
        """
        Send the object from client to server.
        Return the server's idea of the object.
        """
        self.debug('sending object %r from broker %r' % (
            object, self.client.remoteRoot.broker))
        d = self.client.remoteRoot.callRemote('receive', object)
        d.addCallback(lambda r: self.manager.root.object)
        return d

    def receive(self, object):
        """
        Receive the object from server to client.
        Return the client's idea of the object.
        """
        self.debug('receiving object %r' % object)
        d = self.manager.root.clientReference.callRemote('receive', object)
        d.addCallback(lambda r: self.client.object)
        return d


class TestCaseWithManager(TestCase):

    def setUp(self):
        from flumotion.twisted import pb
        from flumotion.common import server, connection
        from flumotion.manager import manager, config
        from StringIO import StringIO

        managerConf = """
        <planet>
        <manager name="planet">
            <host>localhost</host>
            <port>0</port>
            <transport>tcp</transport>
            <component name="manager-bouncer" type="htpasswdcrypt-bouncer">
              <property name="data"><![CDATA[
        user:PSfNpHTkpTx1M
        ]]></property>
            </component>
          </manager>
        </planet>
        """

        conf = config.ManagerConfigParser(StringIO(managerConf)).manager
        self.vishnu = manager.Vishnu(conf.name,
                                     unsafeTracebacks=True)
        self.vishnu.loadManagerConfigurationXML(StringIO(managerConf))
        s = server.Server(self.vishnu)
        if conf.transport == "ssl":
            p = s.startSSL(conf.host, conf.port, conf.certificate,
                           configure.configdir)
        elif conf.transport == "tcp":
            p = s.startTCP(conf.host, conf.port)
        self.tport = p
        self.port = p.getHost().port
        i = connection.PBConnectionInfo('localhost', self.port,
                                        conf.transport == 'ssl',
                                        pb.Authenticator(username='user',
                                                         password='test'))
        self.connectionInfo = i

    def _flushErrors(self, *types):
        # This bit about log flushing seems to be necessary with twisted < 2.5.
        try:
            self.flushLoggedErrors(*types)
        except AttributeError:
            from twisted.python import log as tlog
            tlog.flushErrors(*types)

    def tearDown(self):
        from flumotion.common import errors
        self._flushErrors(errors.NotAuthenticatedError)

        d = self.vishnu.shutdown()
        d.addCallback(lambda _: self.tport.stopListening())
        return d


def _diff(old, new, desc):
    import difflib
    lines = difflib.unified_diff(old, new)
    lines = list(lines)
    if not lines:
        return
    output = ''
    for line in lines:
        output += '%s: %s\n' % (desc, line[:-1])

    raise AssertionError(
        ("\nError while comparing strings:\n"
         "%s") % (output, ))


def diffStrings(orig, new, desc='input'):

    def _tolines(s):
        return [line + '\n' for line in s.split('\n')]

    return _diff(_tolines(orig),
                 _tolines(new),
                 desc=desc)
