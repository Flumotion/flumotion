# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streamer server
# Copyright (C) 2004 Fluendo
#
# flumotion/component/bouncers/htpasswd.py: an htpasswd-based bouncer
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

import crypt

from twisted.python import components
from twisted.cred import credentials

from flumotion.common import interfaces, keycards, log
from flumotion.component import component
from flumotion.component.bouncers import bouncer

__all__ = ['HTPasswd']

class HTPasswd(bouncer.Bouncer):

    logCategory = 'htpasswd'

    def __init__(self, name, filename, data, type):
        bouncer.Bouncer.__init__(self, name)
        self._filename = filename
        self._data = data
        self._type = type

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
            name, password = line.strip().split(':')
            self._db[name] = password

        self.debug('parsed %s, %d lines' % (self._filename or '<memory>',
            len(lines)))
   
    def authenticate(self, keycard):
        if not components.implements(keycard, credentials.ICredentials):
            self.warn('keycard %r does not implement ICredentials', keycard)
            raise AssertionError

        if not self._db.has_key(keycard.username):
            self.info('keycard %r refused, no username %s found' % (
                keycard, keycard.username))
            return None
                                                                                
        entry = self._db[keycard.username]
        if self._type == 'crypt':
            salt = entry[:2]
            encrypted = crypt.crypt(keycard.password, salt)
            if entry == encrypted:
                return self._authenticated(keycard, "crypt accepted")
            else:
                return self._refused(keycard, "crypt refused")
        elif self._type == 'plaintext':
            # if it has this method, like for pb auth, use it
            if hasattr(keycard, 'checkPassword'):
                if keycard.checkPassword(entry):
                    return self._authenticated(keycard, "plaintext accepted")
                else:
                    return self._refused(keycard, "plaintext refused")
            raise NotImplementedError
        elif self._type == 'md5':
            raise NotImplementedError
        else:
            raise AssertionError("unsupported method: %s" % self._type)
                                                                                

    def _authenticated(self, keycard, reason):
        self.info('keycard %r authenticated (%s)' % (keycard, reason))
        self._addKeycard(keycard)
        return keycard
    def _refused(self, keycard, reason):
        self.info('keycard %r refused (%s)' % (keycard, reason))
        return None

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
        # FIXME
        raise

    # FIXME: use checker, get type correctly too
    type = config.get('encryption', 'crypt')
    comp = HTPasswd(config['name'], filename, data, type)
    return comp
