# -*- Mode: Python -*-
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

"""opening a telnet or ssh manhole
"""

import base64
import binascii
import os

from twisted import conch

from twisted.conch import error, manhole
from twisted.conch.insults import insults
from twisted.conch.ssh import keys
from twisted.cred import credentials, portal
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer, reactor
from twisted.python import failure
from zope import interface

from flumotion.common import log

__version__ = "$Rev$"


# This class is from twisted.conch.checkers, copyright 2001-2007 Paul
# Swartz, Jp Calderone, and others. Original license:
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# It has been modified to check a particular authorized_keys file
# instead of poking in users' ~/.ssh directories.


class SSHPublicKeyChecker(log.Loggable):
    try:
        credentialInterfaces = credentials.ISSHPrivateKey,
    except AttributeError:
        log.warning('manhole', 'ssh manhole unavailable (old twisted)')
        # you won't be able to log anything in
        credentialInterfaces = ()

    interface.implements(ICredentialsChecker)

    def __init__(self, authorizedKeysFile):
        self.authorizedKeysFile = authorizedKeysFile

    def requestAvatarId(self, credentials):
        d = defer.maybeDeferred(self.checkKey, credentials)
        d.addCallback(self._cbRequestAvatarId, credentials)
        d.addErrback(self._ebRequestAvatarId)
        return d

    def _cbRequestAvatarId(self, validKey, credentials):
        if not validKey:
            return failure.Failure(UnauthorizedLogin())
        if not credentials.signature:
            return failure.Failure(error.ValidPublicKey())
        else:
            try:
                if conch.version.major < 10:
                    pubKey = keys.getPublicKeyObject(data=credentials.blob)
                    if keys.verifySignature(pubKey, credentials.signature,
                                            credentials.sigData):
                        return credentials.username
                else:
                    pubKey = keys.Key.fromString(credentials.blob)
                    if pubKey.verify(credentials.signature,
                        credentials.sigData):
                        return credentials.username

            except: # any error should be treated as a failed login
                f = failure.Failure()
                log.warning('manhole',
                    'error checking signature on creds %r: %r',
                        credentials, log.getFailureMessage(f))
                return f
        return failure.Failure(UnauthorizedLogin())

    def checkKey(self, credentials):
        filename = self.authorizedKeysFile
        if not os.path.exists(filename):
            return 0
        lines = open(filename).xreadlines()
        for l in lines:
            l2 = l.split()
            if len(l2) < 2:
                continue
            try:
                if base64.decodestring(l2[1]) == credentials.blob:
                    return 1
            except binascii.Error:
                continue
        return 0

    def _ebRequestAvatarId(self, f):
        if not f.check(UnauthorizedLogin, error.ValidPublicKey):
            log.warning('manhole', 'failed login: %r',
                log.getFailureMessage(f))
            return failure.Failure(UnauthorizedLogin())
        return f


def openSSHManhole(authorizedKeysFile, namespace, portNum=-1):
    from twisted.conch import manhole_ssh

    def makeProtocol():
        return insults.ServerProtocol(manhole.Manhole, namespace)
    checker = SSHPublicKeyChecker(authorizedKeysFile)
    sshRealm = manhole_ssh.TerminalRealm()
    sshRealm.chainedProtocolFactory = makeProtocol
    sshPortal = portal.Portal(sshRealm, [checker])
    sshFactory = manhole_ssh.ConchFactory(sshPortal)
    port = reactor.listenTCP(portNum, sshFactory, interface='localhost')
    return port


def openAnonymousTelnetManhole(namespace, portNum=-1):
    from twisted.conch import telnet
    from twisted.internet import protocol

    def makeProtocol():
        return telnet.TelnetTransport(telnet.TelnetBootstrapProtocol,
                                      insults.ServerProtocol,
                                      manhole.Manhole, namespace)

    telnetFactory = protocol.ServerFactory()
    telnetFactory.protocol = makeProtocol
    port = reactor.listenTCP(portNum, telnetFactory,
                             interface='localhost')
    return port
