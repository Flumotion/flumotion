# -*- Mode: Python; test-case-name:flumotion.test.test_workerconfig -*-
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

"""
Parsing of configuration files.
"""

import os
from xml.dom import minidom, Node
from xml.parsers import expat

from flumotion.common import log, common

__version__ = "$Rev$"


class ConfigError(Exception):
    pass


class ConfigEntryManager:
    "I represent a <manager> entry in a worker config file"

    def __init__(self, host, port, transport):
        self.host = host
        self.port = port
        self.transport = transport


class ConfigEntryAuthentication:
    "I represent a <authentication> entry in a worker config file"

    def __init__(self, username, password):
        self.username = username
        self.password = password


class WorkerConfigXML(log.Loggable):
    logCategory = 'config'

    def __init__(self, filename, string=None):
        self.name = None
        self.manager = None
        self.authentication = None
        self.feederports = None
        self.fludebug = None
        self.randomFeederports = False

        try:
            if filename != None:
                self.debug('Loading configuration file `%s\'' % filename)
                self.doc = minidom.parse(filename)
            else:
                self.doc = minidom.parseString(string)
        except expat.ExpatError, e:
            raise ConfigError("XML parser error: %s" % e)

        if filename != None:
            self.path = os.path.split(filename)[0]
        else:
            self.path = None

        self.parse()

    # FIXME: privatize, called from __init__

    def parse(self):
        # <worker name="default">
        #     <manager>
        #     <authentication>
        #     ...
        # </worker>

        root = self.doc.documentElement

        if not root.nodeName == 'worker':
            raise ConfigError("unexpected root node': %s" % root.nodeName)

        if root.hasAttribute('name'):
            self.name = str(root.getAttribute('name'))

        for node in root.childNodes:
            if (node.nodeType == Node.TEXT_NODE or
                node.nodeType == Node.COMMENT_NODE):
                continue
            if node.nodeName == 'manager':
                self.manager = self.parseManager(node)
            elif node.nodeName == 'authentication':
                self.authentication = self.parseAuthentication(node)
            elif node.nodeName == 'feederports':
                self.feederports, self.randomFeederports = \
                    self.parseFeederports(node)
            elif node.nodeName == 'debug':
                self.fludebug = str(node.firstChild.nodeValue)
            else:
                raise ConfigError("unexpected node under '%s': %s" % (
                    root.nodeName, node.nodeName))

    def parseManager(self, node):
        # <manager>
        #   <host>...</host>
        #   <port>...</port>
        #   <transport>...</transport>
        # </manager>

        host = None
        port = None
        transport = None
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue

            if child.nodeName == "host":
                if child.firstChild:
                    host = str(child.firstChild.nodeValue)
                else:
                    host = 'localhost'
            elif child.nodeName == "port":
                if not child.firstChild:
                    raise ConfigError("<port> value must not be empty")
                try:
                    port = int(child.firstChild.nodeValue)
                except ValueError:
                    raise ConfigError("<port> value must be an integer")
            elif child.nodeName == "transport":
                if not child.firstChild:
                    raise ConfigError("<transport> value must not be empty")
                transport = str(child.firstChild.nodeValue)
                if not transport in ('tcp', 'ssl'):
                    raise ConfigError("<transport> must be ssl or tcp")

            else:
                raise ConfigError("unexpected '%s' node: %s" % (
                    node.nodeName, child.nodeName))

        return ConfigEntryManager(host, port, transport)

    def parseAuthentication(self, node):
        # <authentication>
        #   <username>...</username>
        #   <password>...</password>
        # </authentication>

        username = None
        password = None
        for child in node.childNodes:
            if (child.nodeType == Node.TEXT_NODE or
                child.nodeType == Node.COMMENT_NODE):
                continue

            if child.nodeName == "username":
                username = str(child.firstChild.nodeValue)
            elif child.nodeName == "password":
                password = str(child.firstChild.nodeValue)
            else:
                raise ConfigError("unexpected '%s' node: %s" % (
                    node.nodeName, child.nodeName))

        return ConfigEntryAuthentication(username, password)

    def parseFeederports(self, node):
        """
        Returns a list of feeder ports to use (possibly empty),
        and whether or not to use random feeder ports.

        @rtype: (list, bool)
        """
        # returns a list of allowed port numbers
        # port := int
        # port-range := port "-" port
        # port-term := port | port-range
        # port-list := "" | port-term | port-term "," port-list
        # <feederports>port-list</feederports>
        random = False
        if node.hasAttribute('random'):
            random = common.strToBool(node.getAttribute('random'))
        ports = []
        if not node.firstChild:
            return (ports, random)
        terms = str(node.firstChild.nodeValue).split(',')
        for term in terms:
            if '-' in term:
                (lower, upper) = [int(x) for x in term.split('-')]
                if lower > upper:
                    raise ConfigError("<feederports> has an invalid range: "
                            "%s > %s " % (lower, upper))
                for port in range(lower, upper+1):
                    if port not in ports:
                        ports.append(port)
            else:
                port = int(term)
                if port not in ports:
                    ports.append(port)
        return (ports, random)
