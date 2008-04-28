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

from cStringIO import StringIO
from xml.sax.saxutils import quoteattr

__version__ = "$Rev$"


class XMLWriter(object):
    def __init__(self):
        self._data = StringIO()
        self._tagStack = []
        self._indent = 0

    # Private

    def _collectAttributes(self, attributes):
        attrValue = ''
        if attributes:
            for attr, value in attributes:
                assert value is not None, attr
                attrValue += ' %s=%s' % (attr, quoteattr(value))
        return attrValue

    def _openTag(self, tagName, attributes=None):
        attrs = self._collectAttributes(attributes)
        self.writeLine('<%s%s>' % (tagName, attrs))

    def _closeTag(self, tagName):
        self.writeLine('</%s>' % (tagName,))

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
        self._data.write('%s%s\n' % (' ' * self._indent, line))

    def writeTagWithData(self, tagName, data, attributes=None):
        """Writes out and closes a tag. Optionally writes data as a child node.
        @param tagName: name of the tag
        @param data: data or None
        @param attributes: attributes or None
        """
        attrs = self._collectAttributes(attributes)
        if data is None:
            self.writeLine('<%s%s/>' % (tagName, attrs))
        else:
            self.writeLine('<%s%s>%s</%s>' % (tagName, attrs, data, tagName))

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
        self._indent += 2

    def popTag(self):
        """Decreases the indentation and closes the previously opened tag.
        @returns: name of the closed tag
        """
        self._indent -= 2
        tagName = self._tagStack.pop()
        self._closeTag(tagName)
        return tagName
