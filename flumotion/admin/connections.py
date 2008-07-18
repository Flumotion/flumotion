# -*- Mode: Python; fill-column: 80 -*-
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
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""recent connections"""

import datetime
import os
from xml.dom import minidom, Node

from flumotion.common import log, common
from flumotion.common.connection import PBConnectionInfo, parsePBConnectionInfo
from flumotion.common.errors import OptionError
# FIXME: make pychecker able to suppress shadowed builtins like these
# at the defining site, not caller site
# P2.4
__pychecker__ = 'no-shadowbuiltin'
from flumotion.common.python import sorted
__pychecker__ = ''
from flumotion.configure import configure
from flumotion.twisted.pb import Authenticator

__version__ = "$Rev$"


class RecentConnection(object):
    """
    I am an object representing a recent connection.
    You can access some of my state and update the timestamp
    (eg, when I was last connected to) by calling L{updateTimestamp}.

    @ivar name:      name of the recent connection usually host:port
    @type name:      string
    @ivar host:      hostname
    @type host:      string
    @ivar filename:  filename of the connection
    @type filename:  string
    @ivar info:      connection info
    @type info:      L{PBConnectionInfo}
    @ivar timestamp: timestamp
    @type timestamp: datetime.datetime
    """
    def __init__(self, host, filename, info):
        self.name = str(info)
        self.host = host
        self.filename = filename
        self.info = info
        self.timestamp = datetime.datetime.fromtimestamp(
            os.stat(filename).st_ctime)

    def updateTimestamp(self):
        os.utime(self.filename, None)


def _getRecentFilenames():
    # DSU, or as perl folks call it, a Schwartz Transform
    common.ensureDir(configure.registrydir, "registry dir")

    for filename in os.listdir(configure.registrydir):
        filename = os.path.join(configure.registrydir, filename)
        if filename.endswith('.connection'):
            yield filename

def hasRecentConnections():
    """
    Returns if we have at least one recent connection
    @returns: if we have a recent connection
    @rtype: bool
    """
    gen = _getRecentFilenames()
    try:
        gen.next()
    except StopIteration:
        return False

    return True

def getRecentConnections():
    """
    Fetches a list of recently used connections
    @returns: recently used connections
    @rtype: list of L{RecentConnection}
    """
    def _parseConnection(filename):
        tree = minidom.parse(filename)
        state = {}
        for childNode in tree.documentElement.childNodes:
            if (childNode.nodeType != Node.TEXT_NODE and
                childNode.nodeType != Node.COMMENT_NODE):
                state[childNode.nodeName] = childNode.childNodes[0].wholeText
        state['port'] = int(state['port'])
        state['use_insecure'] = (state['use_insecure'] != '0')
        authenticator = Authenticator(username=state['user'],
                                      password=state['passwd'])
        return PBConnectionInfo(state['host'], state['port'],
                                not state['use_insecure'],
                                authenticator)

    recentFilenames = _getRecentFilenames()
    recentConnections = []
    for filename in sorted(recentFilenames, reverse=True):
        try:
            state = _parseConnection(filename)
            recentConnections.append(
                RecentConnection(str(state),
                                 filename=filename,
                                 info=state))
        except Exception, e:
            log.warning('connections', 'Error parsing %s: %r', filename, e)
    return recentConnections

def parsePBConnectionInfoRecent(managerString, use_ssl=True,
                                defaultPort=configure.defaultSSLManagerPort):
    """The same as L{flumotion.common.connection.parsePBConnectionInfo},
    but fills in missing information from the recent connections cache
    if possible.
    @param managerString: manager string we should connect to
    @type managerString: string
    @param use_ssl: True if we should use ssl
    @type use_ssl: bool
    @param defaultPort: default port to use
    @type defaultPort: int
    @returns: connection info
    @rtype: a L{PBConnectionInfo}
    """
    recent = getRecentConnections()
    if not managerString:
        if recent:
            return recent[0].info
        else:
            raise OptionError('No string given and no recent '
                              'connections to use')

    info = parsePBConnectionInfo(managerString, username=None,
                                 password=None,
                                 port=defaultPort,
                                 use_ssl=use_ssl)

    def compatible(i1, i2):
        if i1.port and i1.port != i2.port:
            return False
        if i1.use_ssl != i2.use_ssl:
            return False
        a1, a2 = i1.authenticator, i2.authenticator
        if a1.username and a1.username != a2.username:
            return False
        if a1.password and a1.password != a2.password:
            return False
        return True

    if not info.authenticator.username:
        for c in recent:
            recent = c.info
            if compatible(info, recent):
                info.authenticator.username = recent.authenticator.username
                info.authenticator.password = recent.authenticator.password
                break
    elif not info.authenticator.password:
        for c in recent:
            recent = c.info
            if compatible(info, recent):
                info.authenticator.password = recent.authenticator.password
                break
    if not (info.authenticator.username and info.authenticator.password):
        raise OptionError('You are connecting to %s for the '
                          'first time; please specify a user and '
                          'password (e.g. user:test@%s).'
                          % (managerString, managerString))
    else:
        return info
