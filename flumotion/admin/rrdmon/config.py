# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
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

import os

from xml.dom import Node

from flumotion.configure import configure
from flumotion.common import common, config, connection
from flumotion.common.errors import ConfigError


class ConfigParser(config.BaseConfigParser):
    """
    RRD monitor configuration file parser.

    Create a parser via passing the name of the file to parse to
    __init__. Parse into a dict of properly-typed options by calling
    parse() on the parser.
    """
    logCategory = 'rrdmon-config'

    def __init__(self, file, rrdBaseDir=None):
        """
        @param file: The path to the config file to parse, or a file object
        @type  file: str or file
        @param rrdBaseDir: The base directory for resolving filenames, or None to
                        infer from the path passed
        @type rrdBaseDir: str or None
        """
        if rrdBaseDir is not None:
            self.rrdBaseDir = rrdBaseDir
        else:
            self.rrdBaseDir = os.path.dirname(file)
        config.BaseConfigParser.__init__(self, file)

    def _parseArchive(self, node):
        def strparser(parser):
            def parsestr(node):
                return self.parseTextNode(node, parser)
            return parsestr
        def ressetter(k):
            def setter(v):
                res[k] = v
            return setter

        res = {}
        table = {}
        basicOptions = (('rra-spec', True, str, None),)
        for k, required, parser, default in basicOptions:
            table[k] = strparser(parser), ressetter(k)
            if not required:
                res[k] = default

        self.parseFromTable(node, table)

        for k, required, parser, default in basicOptions:
            if required and k not in res:
                raise config.ConfigError('missing required node %s' % k)
        return res

    def _parseSource(self, node):
        def strparser(parser):
            def parsestr(node):
                return self.parseTextNode(node, parser)
            return parsestr
        def ressetter(k):
            def setter(v):
                res[k] = v
            return setter

        name, = self.parseAttributes(node, ('name',))

        res = {'name': name}
        table = {}

        basicOptions = (('manager', True,
                         connection.parsePBConnectionInfo, None),
                        ('ui-state-key', True, str, None),
                        ('sample-frequency', False, float, 300),
                        ('is-gauge', False, common.strToBool, True),
                        ('rrd-ds-spec', False, str, None),
                        ('rrd-file', False, str, None))
        for k, required, parser, default in basicOptions:
            table[k] = strparser(parser), ressetter(k)
            if not required:
                res[k] = default

        res['archives'] = []
        table['archive'] = (self._parseArchive, res['archives'].append)

        self.parseFromTable(node, table)

        for k, required, parser, default in basicOptions:
            if required and k not in res:
                raise config.ConfigError('missing required node %s' % k)
        if not res['archives']:
            raise config.ConfigError('must specify at least one '
                                     '<archive> per <source>')
            
        return res

    def parse(self):
        # <rrdmon>
        #   <propName>propValue</propName>
        root = self.doc.documentElement
        if not root.nodeName == 'rrdmon':
            raise ConfigError("unexpected root node: %s" % root.nodeName)
        
        def strparser(parser):
            def parsestr(node):
                return self.parseTextNode(node, parser)
            return parsestr
        def ressetter(k):
            def setter(v):
                res[k] = v
            return setter

        res = {'debug': None,
               'sources': []}
        table = {'debug': (strparser(str), ressetter('debug')),
                 'source': (self._parseSource, res['sources'].append)}

        self.parseFromTable(root, table)

        if not res['sources']:
            raise config.ConfigError('must specify at least one '
                                     '<source>')

        return res
