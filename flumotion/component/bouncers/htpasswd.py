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

from flumotion.common import interfaces, keycards
from flumotion.component import component
from flumotion.component.bouncers import bouncer

__all__ = ['HTPasswd']

class HTPasswd(bouncer.Bouncer):

    logCategory = 'htpasswd'

    def __init__(self, name, filename, type):
        bouncer.Bouncer.__init__(self, name)
        self._filename = filename
        self._type = type

        # FIXME: done through state/mood change ?
        self._setup()

    # FIXME: generalize to a start method, possibly linked to mood
    def _setup(self):
        self._db = {}
        lines = open(self._filename).readlines()

        for line in lines:
            name, password = line[:-1].split(':')
            self._db[name] = password

        self.debug('parsed %s, %d lines' % (self._filename, len(lines)))
   
    def authenticate(self, keycard):
        if not components.implements(keycard, credentials.ICredentials):
            self.warn('keycard %r does not implement ICredentials', keycard)
            raise AssertionError

        if not self._db.has_key(keycard.username):
            return None
                                                                                
        entry = self._db[keycard.username]
        if self._type == 'crypt':
            salt = entry[:2]
            encrypted = crypt.crypt(keycard.password, salt)
        elif self._type == 'md5':
            raise NotImplementedError
        else:
            raise AssertionError("unsupported method: %s" % self.type)
                                                                                
        if entry == encrypted:
            self.info('keycard %r authenticated' % keycard)
            self._addKeycard(keycard)
            return keycard
        else:
            self.info('keycard %r refused' % keycard)
            return None

def createComponent(config):
    filename = config['filename']
    # FIXME: use checker
    type = config.get('auth-type', 'crypt')
    comp = HTPasswd(config['name'], filename, type)
    return comp
