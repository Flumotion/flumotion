# -*- Mode: Python; -*-
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
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""xml serializer and component comparison
"""

from cStringIO import StringIO
from xml.sax.saxutils import quoteattr

__version__ = "$Rev$"


class XMLWriter(object):

    def __init__(self):
        self._data = StringIO()
        self._tagStack = []
        self._indent = 0
        self._indentChar = ' '
        self._indentUnit = 2

    # Private

    def _calcAttrsLength(self, attributes, indent):
        if indent == -1:
            return -1
        attrLength = 0
        for attr, value in attributes:
            if value is None:
                raise ValueError(
                    "value for attribute %s cannot be None" % (attr, ))
            attrLength += 1 + len(attr) + len(quoteattr(value))
        return attrLength + indent

    def _collectAttributes(self, attributes, indent=-1):
        if not attributes:
            return ''

        if self._calcAttrsLength(attributes, indent) > 79:
            indentLen = self._indent + indent
        else:
            indentLen = 0
        first = True
        attrValue = ''
        for attr, value in attributes:
            if indentLen and not first:
                attrValue += '\n%s' % (self._indentChar * indentLen)
            if value is None:
                raise ValueError(
                    "value for attribute %s cannot be None" % (attr, ))
            attrValue += ' %s=%s' % (attr, quoteattr(value))
            if first:
                first = False
        return attrValue

    def _openTag(self, tagName, attributes=None):
        attrs = self._collectAttributes(
            attributes, len(tagName) + 1)
        self.writeLine('<%s%s>' % (tagName, attrs))

    def _closeTag(self, tagName):
        self.writeLine('</%s>' % (tagName, ))

    # Public API

    def getXML(self):
        """Fetches the xml written by the writer
        @returns: the xml
        @rtype: string
        """
        return self._data.getvalue()

    def writeLine(self, line=''):
        """Write a line to the xml.
        This method honors the current indentation.
        """
        self._data.write('%s%s\n' % (self._indentChar * self._indent, line))

    def writeTag(self, tagName, attributes=None, data=None):
        """Writes out and closes a tag. Optionally writes data as a child node.
        @param tagName: name of the tag
        @param attributes: attributes or None
        @param data: data or None
        """
        if attributes is None:
            attributes = []
        prefix = '<%s' % (tagName, )
        if data is not None:
            suffix = '>%s</%s>' % (data, tagName)
        else:
            suffix = '/>'
        attrs = self._collectAttributes(
            attributes, len(prefix) + len(suffix))
        self.writeLine(prefix + attrs + suffix)

    def pushTag(self, tagName, attributes=None):
        """Push a tag::
          - writes the tag and the attributes
          - increase the indentation for subsequent calls
        @param tagName: name of the tag to write
        @type tagName: string
        @param attributes: attributes to write
        @type attributes: list of 2 sizes tuples; (name, value)
        """
        self._openTag(tagName, attributes)
        self._tagStack.append(tagName)
        self._indent += self._indentUnit

    def popTag(self):
        """Decreases the indentation and closes the previously opened tag.
        @returns: name of the closed tag
        """
        self._indent -= self._indentUnit
        tagName = self._tagStack.pop()
        self._closeTag(tagName)
        return tagName


def cmpComponentType(aType, bType):
    """Compare two component types the way they should be written in an xml
    file. Suitable for using as cmp argument to list.sort() or sorted().
    @param aType: first component type
    @type aType:
    @param bType: second component type
    @type bType:
    @returns: -1, 0 or 1, see L{__builtin__.cmp}
    """
    for suffix in ['-producer',
                   '-converter',
                   '-encoder',
                   '-muxer',
                   '-streamer']:
        bHasSuffix = bType.endswith(suffix)
        if aType.endswith(suffix):
            if bHasSuffix:
                return cmp(aType, bType)
            else:
                return -1
        elif bHasSuffix:
            return 1
    return cmp(aType, bType)
