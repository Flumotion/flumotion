# -*- Mode: Python; test-case-name: flumotion.test.test_common_componentui -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.common.testsuite import TestCase
from flumotion.common.xmlwriter import cmpComponentType, XMLWriter


class TestXMLWriter(TestCase):

    def testIndent(self):
        xw = XMLWriter()
        xw.pushTag('tag',
                  [('long-attribute-name-number-one', 'value'),
                   ('long-attribute-name-number-two', 'value'),
                   ('long-attribute-name-number-three', 'value')])
        xw.popTag()
        self.assertEquals(
            xw.getXML(),
            ('<tag long-attribute-name-number-one="value"\n'
             '     long-attribute-name-number-two="value"\n'
             '     long-attribute-name-number-three="value">\n'
             '</tag>\n'))

    def testPush(self):
        xw = XMLWriter()
        xw.pushTag('first')
        self.assertEquals(xw.getXML(), "<first>\n")
        xw.popTag()
        self.assertEquals(xw.getXML(), "<first>\n</first>\n")

        xw = XMLWriter()
        xw.pushTag('first', [('attr1', 'a'),
                             ('attr2', 'b')])
        self.assertEquals(xw.getXML(), '<first attr1="a" attr2="b">\n')
        xw.popTag()

    def testWriteLine(self):
        xw = XMLWriter()
        xw.writeLine('foo')
        self.assertEquals(xw.getXML(), 'foo\n')
        xw.pushTag('tag')
        self.assertEquals(xw.getXML(), 'foo\n<tag>\n')
        xw.writeLine('bar')
        self.assertEquals(xw.getXML(), 'foo\n<tag>\n  bar\n')

    def testWriteTag(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2')
        self.assertEquals(xw.getXML(),
                          '<tag>\n  <tag2/>\n')

    def testWriteTagAttr(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2', [('attr', 'value')])
        self.assertEquals(xw.getXML(),
                          '<tag>\n  <tag2 attr="value"/>\n')

    def testWriteTagAttrData(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2', [('attr', 'value')], data='data')
        self.assertEquals(xw.getXML(),
                          '<tag>\n  <tag2 attr="value">data</tag2>\n')

    def testWriteTagData(self):
        xw = XMLWriter()
        xw.pushTag('tag')
        xw.writeTag('tag2', data='data')
        self.assertEquals(xw.getXML(),
                          '<tag>\n  <tag2>data</tag2>\n')


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
