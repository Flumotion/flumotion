# -*- Mode: Python; fill-column: 80 -*-
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

"""recent connections"""

import datetime
import fnmatch
import os
from xml.dom import minidom, Node

from flumotion.common import log, common, xdg
from flumotion.common.connection import PBConnectionInfo, parsePBConnectionInfo
from flumotion.common.errors import OptionError
from flumotion.configure import configure
from flumotion.twisted.pb import Authenticator

__version__ = "$Rev$"


class ConnectionInfo(object):
    """
    I wrap the information contained in a single connection file entry.

    I can be used to construct L{PBConnectionInfo} object, but because some of
    my variables can be shell globs, they are all strings.
    """

    def __init__(self, host, port, use_insecure, user, passwd, manager):
        self.host = host
        self.port = port
        self.use_insecure = use_insecure
        self.user = user
        self.passwd = passwd
        self.manager = manager

    def asPBConnectionInfo(self):
        """
        Return a L{PBConnectionInfo} object constructed from my state. If my
        state contains shell globs, I might throw a ValueError.
        """
        if ('*' in self.host) or (self.use_insecure not in ('0', '1')):
            raise ValueError("Shell glob in connection info")
        return PBConnectionInfo(self.host, int(self.port),
                                self.use_insecure == '0',
                                Authenticator(username=self.user,
                                              password=self.passwd))

    def __str__(self):
        return '%s@%s:%s' % (self.user, self.host, self.port)


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
        self.info = info.asPBConnectionInfo()
        self.manager = info.manager
        self.timestamp = datetime.datetime.fromtimestamp(
            os.stat(filename).st_ctime)

    def updateTimestamp(self):
        os.utime(self.filename, None)

    def asConnectionInfo(self):
        """
        Return a L{ConnectionInfo} object constructed from my state.
        """
        info = self.info
        return ConnectionInfo(info.host, str(info.port),
                              info.use_ssl and '0' or '1',
                              info.authenticator.username,
                              info.authenticator.password, '')


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


def _parseConnection(element):
    state = {}
    for childNode in element.childNodes:
        if (childNode.nodeType != Node.TEXT_NODE and
            childNode.nodeType != Node.COMMENT_NODE):
            state[childNode.nodeName] = childNode.childNodes[0].wholeText
    return ConnectionInfo(state['host'], state['port'], state['use_insecure'],
                          state['user'], state['passwd'], state['manager'])


def _parseSingleConnectionFile(filename):
    tree = minidom.parse(filename)
    return _parseConnection(tree.documentElement)


def _parseMultipleConnectionsFile(filename):
    tree = minidom.parse(filename)
    return map(_parseConnection, tree.getElementsByTagName('connection'))


def getRecentConnections():
    """
    Fetches a list of recently used connections
    @returns: recently used connections
    @rtype: list of L{RecentConnection}
    """

    recentFilenames = _getRecentFilenames()
    recentConnections = []
    for filename in sorted(recentFilenames, reverse=True):
        try:
            state = _parseSingleConnectionFile(filename)
            recentConnections.append(
                RecentConnection(str(state),
                                 filename=filename,
                                 info=state))
        except Exception, e:
            log.warning('connections', 'Error parsing %s: %r', filename, e)
    return recentConnections


def getDefaultConnections():
    """
    Fetches a list of default connections.

    @returns: default connections
    @rtype: list of L{ConnectionInfo}
    """

    filename = xdg.config_read_path('connections')
    if not filename:
        return []

    try:
        return _parseMultipleConnectionsFile(filename)
    except Exception, e:
        log.warning('connections', 'Error parsing %s: %r', filename, e)
    return []


def updateFromConnectionList(info, connections, match_glob=False):
    """
    Updates the info object with the username and password taken from the list
    of connections.

    @param info:        connection info
    @type info:         L{PBConnectionInfo}
    @param connections: recent or default connections
    @type:              a list of L{ConnectionInfo}
    @param match_glob:  if values of host, port, etc. to be matched between
                        info and the recent or default connections should be
                        treated as shell globs
    @type:              boolean
    @returns:           None
    """

    def match(v1, v2):
        if match_glob:
            # v2 is the candidate, which might be a shell glob
            return fnmatch.fnmatch(v1, v2)
        else:
            return v1 == v2

    def compatible(info, c_info):
        if not match(info.host, c_info.host):
            return False
        port = str(info.port)
        if not match(port, c_info.port):
            return False
        use_insecure = info.use_ssl and '0' or '1'
        if not match(use_insecure, c_info.use_insecure):
            return False
        auth = info.authenticator
        if auth.username and not match(auth.username, c_info.user):
            return False
        # doesn't make sense to match the password, if everything before that
        # matched, we won't fill in anything
        return True

    for candidate in connections:
        if compatible(info, candidate):
            # it's compatible, fill in the variables
            if not info.authenticator.username:
                info.authenticator.username = candidate.user
            if not info.authenticator.password:
                info.authenticator.password = candidate.passwd
            break
    return info


def parsePBConnectionInfoRecent(managerString, use_ssl=True,
                                defaultPort=configure.defaultSSLManagerPort):
    """The same as L{flumotion.common.connection.parsePBConnectionInfo},
    but fills in missing information from the recent connections cache or
    from the default user and password definitions file if possible.
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

    if not (info.authenticator.username and info.authenticator.password):
        recent_infos = [r.asConnectionInfo() for r in recent]
        updateFromConnectionList(info, recent_infos, match_glob=False)
    if not (info.authenticator.username and info.authenticator.password):
        defaults = getDefaultConnections()
        updateFromConnectionList(info, defaults, match_glob=True)
    if not (info.authenticator.username and info.authenticator.password):
        raise OptionError('You are connecting to %s for the '
                          'first time; please specify a user and '
                          'password (e.g. user:test@%s).'
                          % (managerString, managerString))
    else:
        return info
