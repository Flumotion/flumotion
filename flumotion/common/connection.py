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

"""helpers for dealing with Twisted PB connections.
"""

import re

from twisted.spread import pb

from flumotion.common import common
from flumotion.twisted import pb as fpb

__version__ = "$Rev$"


class PBConnectionInfo(pb.Copyable, pb.RemoteCopy):
    """
    I hold information on how to connect to a PB server somewhere. I can
    be transferred over the wire.
    """

    def __init__(self, host, port, use_ssl, authenticator):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.authenticator = authenticator

    def __str__(self):
        # have to use getattr in the case that the authenticator was
        # transferred over the wire, because the remote reference is not
        # an authenticator
        if (self.authenticator
            and getattr(self.authenticator, 'username', None)):
            return '%s@%s:%d' % (self.authenticator.username,
                                 self.host, self.port)
        else:
            return '%s:%d' % (self.host, self.port)

pb.setUnjellyableForClass(PBConnectionInfo, PBConnectionInfo)


_pat = re.compile('^(([^:@]*)(:([^:@]+))?@)?([^:@]+)(:([0-9]+))?$')


def parsePBConnectionInfo(string, username='user', password='test',
                          port=7531, use_ssl=True):
    """
    Parse a string representation of a PB connection into a
    PBConnectionInfo object.

    The expected format is [user[:pass]@]host[:port]. Only the host is
    mandatory. The default values for username, password, and port will
    be taken from the optional username, password and port arguments.

    @param string:   A string describing the PB connection.
    @type  string:   str
    @param username: Default username, or 'user' if not given.
    @type  username: str
    @param password: Default password, or 'test' if not given.
    @type  password: str
    @param port:     Default port, or 7531 if not given.
    @type  port:     int
    @param use_ssl:  Whether to use SSL, or True if not given. Note that
                     there is no syntax in the connection string for specifying
                     whether or not to use SSL; if you want to control this you
                     will have to provide another method.
    @type  use_ssl:  bool

    @rtype: L{PBConnectionInfo}
    """
    auth = fpb.Authenticator(username=username, password=password)
    ret = PBConnectionInfo(None, port, use_ssl, auth)

    matched = _pat.search(string)
    if not matched:
        raise TypeError('Invalid connection string: %s '
                        '(looking for [user[:pass]@]host[/ssl|/tcp][:port])'
                        % string)

    groups = matched.groups()
    for o, k, i, f in ((auth, 'username', 1, str),
                       (auth, 'password', 3, str),
                       (ret, 'host', 4, str),
                       (ret, 'port', 6, int)):
        if groups[i]:
            setattr(o, k, f(groups[i]))
    return ret
