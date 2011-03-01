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

import gst

from twisted.python import failure
from twisted.internet import defer, reactor, interfaces, gtk2reactor
from twisted.web import client, error

from flumotion.common import testsuite
from flumotion.common import log, errors
from flumotion.common.planet import moods
from flumotion.component.converters.video import video
from flumotion.common import gstreamer

from flumotion.test import comptest

attr = testsuite.attr

if not gstreamer.element_factory_exists('deinterlace')\
    or not gstreamer.element_factory_has_property('deinterlace', 'method'):
    skip="GStreamer element 'deinterlace' is too old or doesn't exists"


class TestVideoConverter(comptest.CompTestTestCase, log.Loggable):

    def setUp(self):
        self.tp = comptest.ComponentTestHelper()
        prod = ('videotestsrc is-live=true ! '
                'video/x-raw-rgb,framerate=(fraction)1/2,width=320,height=240,'
                'pixel-aspect-ratio=1/2,interlaced=true')
        self.s = 'flumotion.component.converters.video.video.Converter'

        self.prod = comptest.pipeline_src(prod)

    def tearDown(self):
        comptest.cleanup_reactor()

    @attr('slow')
    def test_running_and_happy(self):
        vc = comptest.ComponentWrapper('video-converter', video.Converter,
                                       name='video-converter',
                                       cfg={'properties':
                                            {'deinterlace-mode': 'disabled'}})

        self.tp.set_flow([self.prod, vc])

        d = self.tp.start_flow()

        # wait for the converter to go happy
        d.addCallback(lambda _: vc.wait_for_mood(moods.happy))
        # let it run for a few seconds
        d.addCallback(lambda _: comptest.delayed_d(5, _))
        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d

    def _test_videoscale(self, res, vc, par, w, h, exact=True):
        p = vc.comp.pipeline.get_by_name("feeder:default-pay")
        c = p.get_static_pad('sink').get_negotiated_caps()[0]
        if exact:
            # values have to match exactly
            self.assertEquals(c['width'], w)
            self.assertEquals(c['height'], h)
            self.assertEquals(c['pixel-aspect-ratio'], par)
        else:
            # 320x240 at 1/2 is  640x240 at 1/4
            num = c['width'] * h * c['pixel-aspect-ratio'].num * par.denom
            den = w * c['height'] * par.num * c['pixel-aspect-ratio'].denom
            self.assertEquals(num, den,
                'w/h/par do not match source: %dx%d at %r vs %dx%d at %r' % (
                    c['width'], c['height'], c['pixel-aspect-ratio'],
                    w, h, par))

    def _videoscale_test(self, properties, par, w, h, exact=False):
        vc = comptest.ComponentWrapper('video-converter', video.Converter,
                                       name='video-converter',
                                       cfg={'properties': properties})
        self.tp.set_flow([self.prod, vc])

        d = self.tp.start_flow()

        # wait for the converter to go happy
        d.addCallback(lambda _: vc.wait_for_mood(moods.happy))
        d.addCallback(self._test_videoscale, vc, par, w, h, exact=exact)
        # let it run for a few seconds
        d.addCallback(lambda _: comptest.delayed_d(2, _))
        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d

    @attr('slow')
    def test_is_square_False(self):
        return self._videoscale_test({'is-square': False,
                                     'deinterlace-mode': 'disabled'},
                                     gst.Fraction(1, 2), 320, 240)

    @attr('slow')
    def test_is_square_True(self):
        return self._videoscale_test({'is-square': True,
                                     'deinterlace-mode': 'disabled'},
                                     gst.Fraction(1, 1), 160, 240)

    @attr('slow')
    # videoscale is free to change both height and par, so use inexact
    # originally this test only checked 640x240 at 1/4, but
    # videoscale in 0.10.29 negotiated to 640x480 at 1/2, which is valid too
    def test_width(self):
        return self._videoscale_test({'width': 640,
                                     'deinterlace-mode': 'disabled'},
                                     gst.Fraction(1, 4), 640, 240,
                                     exact=False)

    @attr('slow')
    def test_height(self):
        return self._videoscale_test({'height': 120,
                                     'deinterlace-mode': 'disabled'},
                                     gst.Fraction(1, 4), 320, 120,
                                     exact=False)

    @attr('slow')
    def test_width_and_square(self):
        return self._videoscale_test({'width': 640,
                                     'is-square': True,
                                     'deinterlace-mode': 'disabled'},
                                     gst.Fraction(1, 1), 640, 960)

    @attr('slow')
    def test_width_height_is_square(self):
        properties = {'width': 123,
                      'height': 321,
                      'is-square': True,
                      'deinterlace-mode': 'disabled'}
        return self._videoscale_test(properties,
                                     gst.Fraction(1, 1), 123, 321)

    def _test_interlaced(self, res, vc, interlaced):
        p = vc.comp.pipeline.get_by_name("feeder:default-pay")
        c = p.get_static_pad('sink').get_negotiated_caps()[0]
        self.assertEquals(c['interlaced'], interlaced)

    @attr('slow')
    def test_deinterlace_auto_True(self):
        properties = {'deinterlace-method': "tomsmocomp"}
        vc = comptest.ComponentWrapper('video-converter', video.Converter,
                                       name='video-converter',
                                       cfg={'properties': properties})

        self.tp.set_flow([self.prod, vc])

        d = self.tp.start_flow()

        # wait for the converter to go happy
        d.addCallback(lambda _: vc.wait_for_mood(moods.happy))
        # let it run for a few seconds
        d.addCallback(lambda _: comptest.delayed_d(10, _))
        d.addCallback(self._test_interlaced, vc, False)
        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d
