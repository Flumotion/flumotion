# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from flumotion.common import log

from flumotion.component import feedcomponent
from flumotion.component.converters.overlay import genimg

import tempfile

class Overlay(feedcomponent.ParseLaunchComponent):
    _filename = None

    def get_pipeline_string(self, properties):
        # due to createComponent entry pointism, we have to import inside our
        # function.  PLEASE MAKE THE PAIN GO AWAY ? <- might not be
        # necessary still

        # GST 0.8

        # we need an element that does RGBA -> AYUV so we can overlay png
        # this got added to ffmpegcolorspace in 0.8.5
        addalpha = 'ffmpegcolorspace'

        import gst
        if gst.gst_version < (0,9):
            from flumotion.worker.checks import video
            if not video.check_ffmpegcolorspace_AYUV():
                # alphacolor element works too for the colorspace conversion,
                # but has bugs for non-multiples of 4 or eight
                addalpha = 'ffmpegcolorspace ! alpha'
                log.info('Using gst-plugins older than 0.8.5, consider '
                         'upgrading if you notice a diagonal green line '
                         'in your video output.')

        source = self.config['source'][0]
        eater = '@ eater:%s @' % source

        # the order here is important; to have our eater be the reference
        # stream for videomixer it needs to be specified last
        pipeline = (
            'filesrc name=source blocksize=100000 ! pngdec ! alphacolor ! '
            'videomixer name=mix ! @ feeder:: @ '
            '%(eater)s ! %(addalpha)s ! mix.' % locals())
        
        return pipeline

    def do_start(self, eatersData, feedersData):
        # create temp file
        (fd, self._filename) = tempfile.mkstemp('flumotion.png')
        os.close(fd)

        props = self.config['properties']

        text = None
        if props.get('show_text', False):
            text = props.get('text', 'set the "text" property')
        genimg.generate_overlay(self._filename,
                                text,
                                props.get('fluendo_logo', False),
                                props.get('cc_logo', False),
                                props.get('xiph_logo', False),
                                props['width'],
                                props['height'])
        
        source = self.get_element('source')
        source.set_property('location', self._filename)

        return feedcomponent.ParseLaunchComponent.do_start(self,
            eatersData, feedersData)

    def stop(self):
        # clean up our temp file
        # FIXME: it would probably be nicer to implement this through hooks
        # since now I do this before chaining, while FeedComp does it after
        # chaining, so it's messy
        feedcomponent.ParseLaunchComponent.stop(self)
        if self._filename:
            self.debug('Removing temporary overlay file %s' % self._filename)
            os.unlink(self._filename)
            self._filename = None
        else:
            self.debug('Temporary overlay already gone, did we not start up correctly ?')
        
