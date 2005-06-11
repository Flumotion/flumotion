# -*- Mode: Python; test-case-name: flumotion.test.test_htpasswdcrypt -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

"""
an htpasswd-backed bouncer with crypt passwords
"""

import md5
import random

from twisted.python import components
from twisted.cred import error

from flumotion.common import interfaces, keycards, log
from flumotion.component import component
from flumotion.component.bouncers import bouncer
from flumotion.twisted import credentials, checkers

# T1.3: suppress components warnings in Twisted 2.0
from flumotion.twisted import compat
compat.filterWarnings(components, 'ComponentsDeprecationWarning')

__all__ = ['HTPasswdCrypt']

class HTPasswdCrypt(bouncer.Bouncer):

    logCategory = 'htpasswdcrypt'
    keycardClasses = (keycards.KeycardUACPP, keycards.KeycardUACPCC)

    def __init__(self, name, filename, data):
        bouncer.Bouncer.__init__(self, name)
        self._filename = filename
        self._data = data
        self._checker = checkers.CryptChecker()
        self._challenges = {} # for UACPCC

        # FIXME: done through state/mood change ?
        self._setup()

    # FIXME: generalize to a start method, possibly linked to mood
    def _setup(self):
        self._db = {}
        if self._filename:
            lines = open(self._filename).readlines()
        else:
            lines = self._data.split("\n")

        for line in lines:
            if not ':' in line: continue
            # when coming from a file, it ends in \n, so strip.
            # for data, we already splitted, so no \n, but strip is fine.
            name, cryptPassword = line.strip().split(':')
            self._db[name] = cryptPassword
            self._checker.addUser(name, cryptPassword)

        self.debug('parsed %s, %d lines' % (self._filename or '<memory>',
            len(lines)))
   
    def _requestAvatarIdCallback(self, PossibleAvatarId, keycard):
        # authenticated, so return the keycard with state authenticated
        keycard.state = keycards.AUTHENTICATED
        self.addKeycard(keycard)
        if not keycard.avatarId:
            keycard.avatarId = PossibleAvatarId
        self.info('authenticated login of "%s"' % keycard.avatarId)
        self.debug('keycard %r authenticated, id %s, avatarId %s' % (keycard, keycard.id, keycard.avatarId))
        
        return keycard

    def _requestAvatarIdErrback(self, failure, keycard):
        failure.trap(error.UnauthorizedLogin)
        # FIXME: we want to make sure the "None" we return is returned
        # as coming from a callback, ie the deferred
        self.removeKeycard(keycard)
        self.info('keycard %r refused, Unauthorized' % keycard)
        return None
    
    def authenticate(self, keycard):
        # FIXME: move checks up in the base class ?
        if not components.implements(keycard, credentials.IUsernameCryptPassword):
            self.warning('keycard %r does not implement IUsernameCryptPassword' % keycard)
        if not self.typeAllowed(keycard):
            self.warning('keycard %r not in type list %r' % (keycard, self.keycardClasses))
            return None

        # at this point we add it so there's an ID for challenge-response
        self.addKeycard(keycard)

        # check if the keycard is ready for the checker, based on the type
        if isinstance(keycard, keycards.KeycardUACPCC):
            # Check if we need to challenge it
            if not keycard.challenge:
                self.debug('putting challenge on keycard %r' % keycard)
                keycard.challenge = credentials.cryptChallenge()
                # cheat: get the salt from the checker directly
                if self._checker.users.has_key(keycard.username):
                    keycard.salt = self._checker.users[keycard.username][:2]
                else:
                    # random-ish salt, otherwise it's too obvious
                    string = str(random.randint(pow(10,10), pow(10, 11)))
                    md = md5.new()
                    md.update(string)
                    keycard.salt = md.hexdigest()[:2]
                    self.debug("user not found, inventing bogus salt")
                self.debug("salt %s, storing challenge for id %s" % (keycard.salt, keycard.id))
                # we store the challenge locally to verify against tampering
                self._challenges[keycard.id] = keycard.challenge
                return keycard

            if keycard.response:
                # Check if the challenge has been tampered with
                if self._challenges[keycard.id] != keycard.challenge:
                    self.removeKeycard(keycard)
                    self.info('keycard %r refused, challenge tampered with' % keycard)
                    return None
                del self._challenges[keycard.id]

        # use the checker
        d = self._checker.requestAvatarId(keycard)
        d.addCallback(self._requestAvatarIdCallback, keycard)
        d.addErrback(self._requestAvatarIdErrback, keycard)
        return d

def createComponent(config):
    # we need either a filename or data
    filename = None
    data = None
    if config.has_key('filename'):
        filename = config['filename']
        log.debug('htpasswd', 'using file %s for passwords' % filename)
    elif config.has_key('data'):
        data = config['data']
        log.debug('htpasswd', 'using in-line data for passwords')
    else:
        raise config.ConfigError(
            'HTPasswdCrypt config needs either a <data> or <filename> entry')

    # FIXME: use checker
    comp = HTPasswdCrypt(config['name'], filename, data)
    return comp
