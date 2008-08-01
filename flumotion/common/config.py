# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
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

"""configuration parsing utilities.
Base classes for parsing of flumotion configuration files
"""

import os
import locale
import sys

from flumotion.common import log, common, registry, fxml
from flumotion.common.errors import ConfigError
from flumotion.common.fraction import fractionFromValue

__version__ = "$Rev$"


def parsePropertyValue(propName, type, value):
    # XXX: We might end up calling float(), which breaks
    #      when using LC_NUMERIC when it is not C -- only in python
    #      2.3 though, no prob in 2.4. See PEP 331
    if sys.version_info < (2, 4):
        locale.setlocale(locale.LC_NUMERIC, "C")

    def tryStr(s):
        try:
            return str(s)
        except UnicodeEncodeError:
            return s

    def strWithoutNewlines(s):
        return tryStr(' '.join([x.strip() for x in s.split('\n')]))

    def boolean(v):
        if isinstance(v, bool):
            return v
        return common.strToBool(v)

    try:
        # yay!
        return {'string': strWithoutNewlines,
                'rawstring': tryStr,
                'int': int,
                'long': long,
                'bool': boolean,
                'float': float,
                'fraction': fractionFromValue}[type](value)
    except KeyError:
        raise ConfigError("unknown type '%s' for property %s"
                          % (type, propName))
    except Exception, e:
        raise ConfigError("Error parsing property '%s': '%s' does not "
                          "appear to be a valid %s.\nDebug: %s"
                          % (propName, value, type,
                             log.getExceptionMessage(e)))


def parseCompoundPropertyValue(name, definition, value):
    if isinstance(value, (list, tuple)):
        try:
            parsed = buildPropertyDict(value, definition.getProperties())
        except ConfigError, ce:
            m = ('(inside compound-property %r) %s' %
                 (name, ce.args[0]))
            raise ConfigError(m)
    # elif isinstance(value, basestring):
    #    FIXME: parse the string representation of the compound property?
    #    pass
    else:
        raise ConfigError('simple value specified where compound property'
                          ' (name=%r) expected' % (name, ))
    return parsed


def buildPropertyDict(propertyList, propertySpecList):
    """Build a property dict suitable for forming part of a component
    config.

    @param propertyList: List of property name-value pairs. For example,
                         [('foo', 'bar'), ('baz', 3)] defines two
                         property-value pairs. The values will be parsed
                         into the appropriate types, this it is allowed
                         to pass the string '3' for an int value.
    @type  propertyList: List of (name, value)
    @param propertySpecList: The set of allowed and required properties
    @type  propertySpecList: List of
                         L{flumotion.common.registry.RegistryEntryProperty}
    """
    ret = {}
    prop_specs = dict([(x.name, x) for x in propertySpecList])
    for name, value in propertyList:
        if not name in prop_specs:
            raise ConfigError('unknown property %s' % (name, ))
        definition = prop_specs[name]

        if isinstance(definition, registry.RegistryEntryCompoundProperty):
            parsed = parseCompoundPropertyValue(name, definition, value)
        else:
            if isinstance(value, (list, tuple)):
                raise ConfigError('compound value specified where simple'
                                  ' property (name=%r) expected' % (name, ))
            parsed = parsePropertyValue(name, definition.type, value)
        if definition.multiple:
            vals = ret.get(name, [])
            vals.append(parsed)
            ret[name] = vals
        else:
            if name in ret:
                raise ConfigError("multiple value specified but not "
                                  "allowed for property %s" % (name, ))
            ret[name] = parsed

    for name, definition in prop_specs.items():
        if definition.isRequired() and not name in ret:
            raise ConfigError("required but unspecified property %s"
                              % (name, ))
    return ret


def buildPlugsSet(plugsList, sockets):
    """Build a plugs dict suitable for forming part of a component
    config.

    @param plugsList: List of plugs, as type-propertyList pairs. For
                      example, [('frag', [('foo', 'bar')])] defines a plug
                      of type 'frag', and the propertyList representing
                      that plug's properties. The properties will be
                      validated against the plug's properties as defined
                      in the registry.
    @type  plugsList: List of (type, propertyList)
    @param sockets: The set of allowed sockets
    @type  sockets: List of str
    """
    ret = {}
    for socket in sockets:
        ret[socket] = []
    for plugType, propertyList in plugsList:
        plug = ConfigEntryPlug(plugType, propertyList)
        if plug.socket not in ret:
            raise ConfigError("Unsupported socket type: %s"
                              % (plug.socket, ))
        ret[plug.socket].append(plug.config)
    return ret


class ConfigEntryPlug(log.Loggable):
    "I represent a <plug> entry in a planet config file"

    def __init__(self, plugType, propertyList):
        try:
            defs = registry.getRegistry().getPlug(plugType)
        except KeyError:
            raise ConfigError("unknown plug type: %s" % plugType)

        self.type = plugType
        self.socket = defs.getSocket()
        self.properties = buildPropertyDict(propertyList,
                                            defs.getProperties())
        self.config = {'type': self.type,
                       'socket': self.socket,
                       'entries': self._parseEntries(defs),
                       'properties': self.properties}

    def _parseEntries(self, entries):
        d = {}
        for entry in entries.getEntries():
            d[entry.getType()] = {
                'module-name': entry.getModuleName(),
                'function-name': entry.getFunction(),
                }
        return d


class BaseConfigParser(fxml.Parser):
    parserError = ConfigError

    def __init__(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        self.add(file)

    def add(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        try:
            self.path = os.path.split(file.name)[0]
        except AttributeError:
            # for file objects without the name attribute, e.g. StringIO
            self.path = None

        try:
            self.doc = self.getRoot(file)
        except fxml.ParserError, e:
            raise ConfigError(e.args[0])

    def getPath(self):
        return self.path

    def parsePlugs(self, node):
        # <plugs>
        #  <plug>
        # returns: list of (socket, type, properties)
        self.checkAttributes(node)

        plugs = []

        def parsePlug(node):
            # <plug type=...>
            #   <property>
            # socket is unneeded and deprecated; we don't use it.
            plugType, socket = self.parseAttributes(
                node, ('type', ), ('socket', ))
            properties = []
            parsers = {'property': (self._parseProperty, properties.append),
                       'compound-property': (self._parseCompoundProperty,
                                             properties.append)}
            self.parseFromTable(node, parsers)
            return plugType, properties

        parsers = {'plug': (parsePlug, plugs.append)}
        self.parseFromTable(node, parsers)
        return plugs

    def _parseProperty(self, node):
        name, = self.parseAttributes(node, ('name', ))
        return name, self.parseTextNode(node, lambda x: x)

    def _parseCompoundProperty(self, node):
        # <compound-property name="name">
        #   <property name="name">value</property>*
        #   <compound-property name="name">...</compound-property>*
        # </compound-property>
        name, = self.parseAttributes(node, ('name', ))
        properties = []
        parsers = {'property': (self._parseProperty, properties.append),
                   'compound-property': (self._parseCompoundProperty,
                                         properties.append)}
        self.parseFromTable(node, parsers)
        return name, properties
