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


"""
RRD monitor configuration parser.

The format of the configuration file is as follows. *, +, and ? have
their normal meanings: 0 or more, 1 or more, and 0 or 1, respectively.

<rrdmon>

  <!-- normal -->
  <debug>*:4</debug> ?

  <!-- implementation note: the name of the source is used as the DS
       name in the RRD file -->
  <source name="http-streamer"> +

    <!-- how we connect to the manager; parsed with
         L{flumotion.common.connection.parsePBConnectionInfo} -->
    <manager>user:test@localhost:7531</manager>

    <!-- the L{flumotion.common.common.componentId} of the component we
         will poll -->
    <component-id>/default/http-audio-video</component-id>

    <!-- the key of the L{flumotion.common.componentui} UIState that we
         will poll; should be numeric in value -->
    <ui-state-key>stream-totalbytes-raw</ui-state-key>

    <!-- boolean; examples of gauge values would be number of users,
         temperature, signal strength, precomputed bitrate. The most
         common non-gauge values are bitrate values, where you poll e.g.
         the number of bytes sent, not the rate itself -->
    <is-gauge>False</is-gauge> ?

    <!-- sample frequency in seconds, defaults to 5 minutes -->
    <sample-frequency>300</sample-frequency> ?

    <!-- Normally we generate the RRD DS spec from the answers above,
         but if you want to you can specify one directly here. The DS
         name should be the source name -->
    <rrd-ds-spec>DS-SPEC</rrd-ds-spec> ?

    <!-- file will be created if necessary -->
    <rrd-file>/tmp/stream-bitrate.rrd</rrd-file>

    <!-- set of archives to store in the rrd file
    <archive> +
      <!-- Would be nice to break this down as we did above for the DS
           spec, but for now you have to specify the RRA specs manually.
           Bummer dude! In this example, the meaning is that we should
           archive a sample every 1*stepsize=1*300s=5 minutes, for 1200
           samples = 5 min*1200=100h.-->
      <rra-spec>AVERAGE:0.5:1:1200</rra-spec>
    </archive>
  </source>

</rrdmon>
"""

import os

from flumotion.common import common
from flumotion.common.connection import parsePBConnectionInfo
from flumotion.common.errors import ConfigError
from flumotion.common.fxml import Parser

__version__ = "$Rev$"


class ConfigParser(Parser):
    """
    RRD monitor configuration file parser.

    Create a parser via passing the name of the file to parse to
    __init__. Parse into a dict of properly-typed options by calling
    parse() on the parser.
    """
    parserError = ConfigError
    logCategory = 'rrdmon-config'

    def __init__(self, file):
        """
        @param file: The path to the config file to parse, or a file object
        @type  file: str or file
        """
        self.doc = self.getRoot(file)

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
        basicOptions = (('rra-spec', True, str, None), )
        for k, required, parser, default in basicOptions:
            table[k] = strparser(parser), ressetter(k)
            if not required:
                res[k] = default

        self.parseFromTable(node, table)

        for k, required, parser, default in basicOptions:
            if required and k not in res:
                raise ConfigError('missing required node %s' % k)
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
        def filename(v):
            if v[0] != os.sep:
                raise ConfigError('rrdfile paths should be absolute')
            return str(v)

        name, = self.parseAttributes(node, ('name', ))

        res = {'name': name}
        table = {}

        basicOptions = (('manager', True,
                         parsePBConnectionInfo, None),
                        ('component-id', True, str, None),
                        ('ui-state-key', True, str, None),
                        ('sample-frequency', False, int, 300),
                        ('is-gauge', False, common.strToBool, True),
                        ('rrd-ds-spec', False, str, None),
                        ('rrd-file', True, filename, None))
        for k, required, parser, default in basicOptions:
            table[k] = strparser(parser), ressetter(k)
            if not required:
                res[k] = default

        res['archives'] = []
        table['archive'] = (self._parseArchive, res['archives'].append)

        self.parseFromTable(node, table)

        for k, required, parser, default in basicOptions:
            if required and k not in res:
                raise ConfigError('missing required node %s' % k)
        if not res['archives']:
            raise ConfigError('must specify at least one '
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
            raise ConfigError('must specify at least one <source>')

        return res
