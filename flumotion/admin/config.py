# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
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
parsing of admin configuration files
"""

from flumotion.common import errors
from flumotion.common import config as fluconfig

__version__ = "$Rev$"


class AdminConfigParser(fluconfig.BaseConfigParser):
    """
    Admin configuration file parser.
    """
    logCategory = 'config'

    def __init__(self, sockets, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        self.plugs = {}
        for socket in sockets:
            self.plugs[socket] = []

        # will start the parse via self.add()
        fluconfig.BaseConfigParser.__init__(self, file)

    def _parse(self):
        # <admin>
        #   <plugs>
        root = self.doc.documentElement
        if not root.nodeName == 'admin':
            raise errors.ConfigError("unexpected root node': %s" %
                (root.nodeName, ))

        def parseplugs(node):
            return fluconfig.buildPlugsSet(self.parsePlugs(node),
                                 self.plugs.keys())

        def addplugs(plugs):
            for socket in plugs:
                self.plugs[socket].extend(plugs[socket])
        parsers = {'plugs': (parseplugs, addplugs)}

        self.parseFromTable(root, parsers)
        self.doc.unlink()
        self.doc = None

    def add(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        fluconfig.BaseConfigParser.add(self, file)
        self._parse()
