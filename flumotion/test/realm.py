# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

from twisted.cred import portal
from twisted.spread import pb
from zope.interface import implements

from flumotion.twisted import pb as fpb
from flumotion.twisted import portal as fportal
from flumotion.common import server, connection, log
from flumotion.configure import configure
from flumotion.component.bouncers import htpasswdcrypt


class TestRealm(log.Loggable):
    implements(portal.IRealm, server.IServable)
    logCategory = 'fakerealm'

    bouncerconf = {'name': 'testbouncer',
                   'plugs': {},
                   # user:test
                   'properties': {'data': "user:qi1Lftt0GZC0o"}}

    def __init__(self):
        self._tport = None
        self._bouncer = None
        self.listen()

    def getPortNum(self):
        assert self._tport is not None
        return self._tport.getHost().port

    def getConnectionInfo(self):
        thost = self._tport.getHost()
        authenticator = fpb.Authenticator(username='user',
                                          password='test')
        return connection.PBConnectionInfo(thost.host, thost.port, True,
                                           authenticator)

    def setConnectionInfo(self, *args):
        # FIXME, this interface method is terribly named, but it's
        # specified in IServable
        pass

    def getFactory(self):
        self._bouncer = htpasswdcrypt.HTPasswdCrypt(self.bouncerconf)

        portal = fportal.BouncerPortal(self, self._bouncer)
        return pb.PBServerFactory(portal, unsafeTracebacks=1)

    def listen(self):
        srv = server.Server(self)
        self._tport = srv.startSSL('localhost', 0, 'default.pem',
                                   configure.configdir)

        self.debug('Listening for feed requests on TCP port %d',
                   self.getPortNum())

    def shutdown(self):
        d = self._tport.stopListening()
        if self._bouncer:
            d.addCallback(lambda _: self._bouncer.stop())
        return d
