# -*- Mode: Python; test-case-name: flumotion.test.test_common_componentui -*-
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

from flumotion.common.testsuite import TestCase
from flumotion.common.xmlwriter import cmpComponentType, XMLWriter


class TestXMLWriter(TestCase):

    def _addXMLHeader(self, xw, doc):
        return xw.encoding + doc

    def testIndent(self):
        xw = XMLWriter()
        xw.pushTag('tag',
                  [('long-attribute-name-number-one', 'value'),
                   ('long-attribute-name-number-two', 'value'),
                   ('long-attribute-name-number-three', 'value')])
        xw.popTag()
        self.assertEquals(
            xw.getXML(),
            self._addXMLHeader(xw,
                ('<tag long-attribute-name-number-one="value"\n'
                '     long-attribute-name-number-two="value"\n'
                '     long-attribute-name-number-three="value">\n'
                '</tag>\n')))

    def testPush(self):
        xw = XMLWriter()
        xw.pushTag('first')
        self.assertEquals(xw.getXML(), self._addXMLHeader(xw, "<first>\n"))
        xw.popTag()
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw, "<first>\n</first>\n"))

        xw = XMLWriter()
        xw.pushTag('first', [('attr1', 'a'),
                             ('attr2', 'b')])
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw,
                            '<first attr1="a" attr2="b">\n'))
        xw.popTag()

    def testWriteLine(self):
        xw = XMLWriter()
        xw.writeLine('foo')
        self.assertEquals(xw.getXML(), self._addXMLHeader(xw, 'foo\n'))
        xw.pushTag('tag')
        self.assertEquals(xw.getXML(), self._addXMLHeader(xw, 'foo\n<tag>\n'))
        xw.writeLine('bar')
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw, 'foo\n<tag>\n  bar\n'))

    def testWriteLineEncoding(self):
        xw = XMLWriter()
        line = unicode("f\xc3\xb6\xc3\xb3", 'utf8')
        xw.writeLine(line)
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw, line.encode('utf8') + '\n'))

    def testWriteTag(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2')
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw, '<tag>\n  <tag2/>\n'))

    def testWriteTagAttr(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2', [('attr', 'value')])
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw,
                            '<tag>\n  <tag2 attr="value"/>\n'))

    def testWriteTagAttrData(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2', [('attr', 'value')], data='data')
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw,
                            '<tag>\n  <tag2 attr="value">data</tag2>\n'))

    def testWriteTagData(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2', data='data')
        self.assertEquals(xw.getXML(),
                          self._addXMLHeader(xw,
                            '<tag>\n  <tag2>data</tag2>\n'))


class TestCompareComponentTypes(TestCase):

    def testEncoderMuxer(self):
        components = ['ogg-muxer',
                      'vorbis-encoder',
                      'theora-encoder']
        components.sort(cmp=cmpComponentType)
        self.assertEquals(components,
                          ['theora-encoder',
                           'vorbis-encoder',
                           'ogg-muxer'],
                          components)

    def testProducerEncoderMuxer(self):
        components = ['ogg-muxer',
                      'vorbis-encoder',
                      'videotest-producer',
                      'theora-encoder']
        components.sort(cmp=cmpComponentType)
        self.assertEquals(components,
                          ['videotest-producer',
                           'theora-encoder',
                           'vorbis-encoder',
                           'ogg-muxer'],
                          components)

    def testComplete(self):
        components = ['ogg-muxer',
                      'http-streamer',
                      'overlay-converter',
                      'vorbis-encoder',
                      'videotest-producer',
                      'dirac-encoder',
                      'audiotest-producer']
        components.sort(cmp=cmpComponentType)
        self.assertEquals(components,
                          ['audiotest-producer',
                           'videotest-producer',
                           'overlay-converter',
                           'dirac-encoder',
                           'vorbis-encoder',
                           'ogg-muxer',
                           'http-streamer'],
                          components)
