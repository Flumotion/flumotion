# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
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

import gettext

from flumotion.common import log
from flumotion.wizard import enums
from flumotion.configure import configure

# FIXME: This is absolutely /horrible/, we should not
#        use translatable string as constants when saving the
#        wizard configuration.
_ = N_ = gettext.gettext
__version__ = "$Rev$"

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)

class Component(log.Loggable):
    logCategory = "componentsave"

    def __init__(self, name, component_type, worker, properties=None, plugs=None):
        self.debug('Creating component %s (%s) worker=%r' % (
            name, type, worker))
        self.name = name
        self.component_type = component_type
        if not properties:
            properties = {}
        self.props = properties
        if not plugs:
            plugs = []
        self.plugs = plugs
        self.worker = worker
        self.eaters = []
        self.feeders = []

    def __repr__(self):
        return '<flumotion.wizard.save.Component name="%s">' % self.name

    def addEater(self, component):
        self.eaters.append(component)

    def addFeeder(self, component):
        self.feeders.append(component)

    def link(self, component):
        self.feeders.append(component)
        component.addEater(self)

    def getFeeders(self):
        s = []
        for source in self.feeders:
            if source.component_type == 'firewire-producer':
                if self.name in ('encoder-video', 'overlay-video'):
                    feed = 'video'
                else:
                    feed = 'audio'
                s.append('%s:%s' % (source.name, feed))
            else:
                s.append(source.name)

        return s

    def toXML(self):
        """
        Write out the XML <component> section for this component.
        """
        extra = ' worker="%s"' % self.worker

        # FIXME: when the wizard can be split among projects, "project"
        # and "version" should be taken from the relevant project
        s = '    <component name="%s" type="%s" ' \
            'project="flumotion" version="%s"%s>\n' % (
            self.name, self.component_type, configure.version, extra)
        whoIsFeedingUs = self.getFeeders()
        if len(whoIsFeedingUs) > 0:
            s += '      <eater name="default">\n'
            for sourceName in whoIsFeedingUs:
                s += "        <feed>%s</feed>\n" % sourceName
            s += '      </eater>\n'

        if self.props:
            s += "\n"
            property_names = self.props.keys()
            property_names.sort()

            #import code; code.interact(local=locals())
            for name in property_names:
                value = self.props[name]
                s += '      <property name="%s">%s</property>\n' % (name, value)

        if self.plugs:
            s += "\n"
            s += '      <plugs>\n'
            for plug in self.plugs:
                s += '      <plug socket="%s" type="%s">\n' % (plug.socket,
                                                               plug.plug_type)
                plugprops = plug.getProperties()
                property_names = plugprops.keys()
                property_names.sort()
                for name in property_names:
                    value = plugprops[name]
                    s += '        <property name="%s">%s</property>\n' % (
                        name, value)
                s += "      </plug>\n"
            s += '      </plugs>\n'
        s += "    </component>\n"
        return s

    def printTree(self, indent=1):
        print indent * '*', self.name, self.component_type, \
              tuple([f.name for f in self.feeders]) or ''
        for eater in self.eaters:
            eater.printTree(indent+1)

class WizardSaver(log.Loggable):
    logCategory = 'wizard-saver'
    def __init__(self, wizard):
        self.wizard = wizard
        self._flow_components = []
        self._atmosphere_components = []

    def _set_fraction_property(self, properties, property_name, denominator):
        if not property_name in properties:
            return

        value = properties[property_name]
        try:
            value = _fraction_from_float(int(value), denominator)
        except ValueError:
            pass
        properties[property_name] = value

    def _getVideoSource(self):
        source_step = self.wizard.get_step('Source')
        video_producer = source_step.get_video_producer()
        properties = video_producer.getProperties()
        self._set_fraction_property(properties, 'framerate', 10)

        return Component('producer-video',
                         video_producer.component_type,
                         video_producer.getWorker(),
                         properties)

    def _getAudioSource(self, video_source):
        source_step = self.wizard.get_step('Source')
        audio_producer = source_step.get_audio_producer()

        # If we selected firewire and have selected video
        # and the selected video is Firewire,
        #   return the source
        if (audio_producer.component_type == 'firewire-producer' and
            video_source and
            video_source.component_type == 'firewire-producer'):
            return video_source

        properties = audio_producer.getProperties()
        self._set_fraction_property(properties, 'framerate', 10)

        return Component('producer-audio',
                         audio_producer.component_type,
                         audio_producer.worker,
                         properties)

    def _getVideoEncoder(self):
        encoding_step = self.wizard.get_step('Encoding')
        video_encoder = encoding_step.get_video_encoder()

        return Component('encoder-video',
                         video_encoder.component_type,
                         video_encoder.getWorker(),
                         video_encoder.getProperties())

    def _getAudioEncoder(self):
        encoding_step = self.wizard.get_step('Encoding')
        audio_encoder = encoding_step.get_audio_encoder()

        return Component('encoder-audio',
                         audio_encoder.component_type,
                         audio_encoder.getWorker(),
                         audio_encoder.getProperties())

    def _getMuxer(self, name):
        encoding_step = self.wizard.get_step('Encoding')
        return Component('muxer-' + name,
                         encoding_step.get_muxer_type(),
                         encoding_step.worker)

    def _handleHTTPConsumer(self, name, step):
        server = step.getServerConsumer()
        if server is not None:
            server = Component('server1',
                               server.component_type,
                               server.getWorker(),
                               server.getProperties(),
                               server.getPlugs())
            self._flow_components.append(server)

        porter = step.getPorter()
        if porter is not None:
            porter = Component('porter1',
                               porter.component_type,
                               porter.getWorker(),
                               porter.getProperties())
            self._atmosphere_components.append(porter)

        streamer = step.getStreamerConsumer()
        return Component(name,
                         streamer.component_type,
                         streamer.getWorker(),
                         streamer.getProperties())

    def getVideoOverlay(self, video_source):
        step = self.wizard.get_step('Overlay')
        properties = step.get_state()

        has_overlay = (step.can_overlay and
                       (properties['show-logo'] or
                        properties['show-text']))
        if not has_overlay:
            del properties['text']
            return

        properties['width'] = video_source.props['width']
        properties['height'] = video_source.props['height']

        # At this point we already know that we should overlay something
        if properties['show-logo']:
            properties['fluendo-logo'] = True
            encoding_step = self.wizard.get_step('Encoding')
            if encoding_step.get_muxer_type() == 'ogg-muxer':
                properties['xiph-logo'] = True

            license_options = self.wizard.get_step_options('Content License')
            if (license_options['set-license']
                and license_options['license'] == enums.LicenseType.CC):
                properties['cc-logo'] = True

        # These were just used to pass capabilities; they shouldn't go into the
        # XML.
        del properties['show-logo']

        return Component('overlay-video', 'overlay-converter',
                         step.worker, properties)

    def handleVideo(self):
        video_source = self._getVideoSource()
        self._flow_components.append(video_source)

        video_encoder = self._getVideoEncoder()
        self._flow_components.append(video_encoder)

        video_overlay = self.getVideoOverlay(video_source)
        if video_overlay:
            video_overlay.link(video_source)
            video_encoder.link(video_overlay)
            self._flow_components.append(video_overlay)
        else:
            video_encoder.link(video_source)
        return video_encoder, video_source

    def handleAudio(self, video_source):
        audio_source = self._getAudioSource(video_source)
        # In case of firewire component, which can already be there
        if not audio_source in self._flow_components:
            self._flow_components.append(audio_source)

        audio_encoder = self._getAudioEncoder()
        self._flow_components.append(audio_encoder)
        audio_encoder.link(audio_source)

        return audio_encoder

    def handleConsumers(self, audio_encoder, video_encoder):
        cons_options = self.wizard.get_step_options('Consumption')
        has_audio = self.wizard.get_step_option('Source', 'has-audio')
        has_video = self.wizard.get_step_option('Source', 'has-video')

        audio_muxer = self._getMuxer('audio')
        video_muxer = self._getMuxer('video')
        both_muxer = self._getMuxer('audio-video')

        steps = []
        if has_audio and has_video:
            if cons_options['http']:
                if cons_options['http-audio-video']:
                    steps.append(('http-audio-video',
                                  'http-streamer',
                                  'HTTP Streamer (audio & video)',
                                  both_muxer))
                if cons_options['http-audio']:
                    steps.append(('http-audio', 'http-streamer',
                                  'HTTP Streamer (audio only)',
                                  audio_muxer))
                if cons_options['http-video']:
                    steps.append(('http-video', 'http-streamer',
                                  'HTTP Streamer (video only)',
                                  video_muxer))
            if cons_options['disk']:
                if cons_options['disk-audio-video']:
                    steps.append(('disk-audio-video',
                                  'disk-consumer',
                                  'Disk (audio & video)',
                                  both_muxer))
                if cons_options['disk-audio']:
                    steps.append(('disk-audio', 'disk-consumer',
                                  'Disk (audio only)', audio_muxer))
                if cons_options['disk-video']:
                    steps.append(('disk-video', 'disk-consumer',
                                  'Disk (video only)', video_muxer))
            if cons_options['shout2']:
                if cons_options['shout2-audio-video']:
                    steps.append(('shout2-audio-video', 'shout2-consumer',
                                  'Icecast streamer (audio & video)',
                                  both_muxer))
                if cons_options['shout2-audio']:
                    steps.append(('shout2-audio', 'shout2-consumer',
                                  'Icecast streamer (audio only)',
                                  audio_muxer))
                if cons_options['shout2-video']:
                    steps.append(('shout2-video', 'shout2-consumer',
                                  'Icecast streamer (video only)',
                                  video_muxer))
        elif has_video and not has_audio:
            if cons_options['http']:
                steps.append(('http-video', 'http-streamer',
                              'HTTP Streamer (video only)', video_muxer))
            if cons_options['disk']:
                steps.append(('disk-video', 'disk-consumer',
                              'Disk (video only)', video_muxer))
            if cons_options['shout2']:
                steps.append(('shout2-video', 'shout2-consumer',
                              'Icecast streamer (video only)', video_muxer))
        elif has_audio and not has_video:
            if cons_options['http']:
                steps.append(('http-audio', 'http-streamer',
                              'HTTP Streamer (audio only)', audio_muxer))
            if cons_options['disk']:
                steps.append(('disk-audio', 'disk-consumer',
                              'Disk (audio only)', audio_muxer))
            if cons_options['shout2']:
                steps.append(('shout2', 'shout2-consumer',
                              'Icecast streamer (audio only)', audio_muxer))
        else:
            raise AssertionError

        for name, comp_type, step_name, muxer in steps:
            if not cons_options.has_key(name):
                continue
            step = self.wizard.get_step(step_name)
            if comp_type == 'http-streamer':
                consumer = self._handleHTTPConsumer(name, step)
            else:
                consumer = Component(
                    name, comp_type,
                    step.worker, step.get_state())

            consumer.link(muxer)
            self._flow_components.append(consumer)

        # Add & link the muxers we will use
        if audio_muxer and audio_muxer.eaters:
            self._flow_components.append(audio_muxer)
            audio_muxer.link(audio_encoder)
        if video_muxer and video_muxer.eaters:
            self._flow_components.append(video_muxer)
            video_muxer.link(video_encoder)
        if both_muxer and both_muxer.eaters:
            self._flow_components.append(both_muxer)
            both_muxer.link(video_encoder)
            both_muxer.link(audio_encoder)

    def _fetchComponentsFromWizardSteps(self):
        source_options = self.wizard.get_step_options('Source')
        has_video = source_options['has-video']
        has_audio = source_options['has-audio']

        video_encoder = None
        video_source = None
        if has_video:
            video_encoder, video_source = self.handleVideo()

        # Must do audio after video, in case of a firewire audio component
        # is selected together with a firewire video component
        audio_encoder = None
        if has_audio:
            audio_encoder = self.handleAudio(video_source)

        self.handleConsumers(audio_encoder, video_encoder)

    def getXML(self):
        # FIXME: allow for naming flows !
        self._fetchComponentsFromWizardSteps()
        flowname = self.wizard.flowName

        s = '<planet>\n'

        if self._atmosphere_components:
            s += '  <atmosphere>\n'
            for component in self._atmosphere_components:
                s += component.toXML() + "\n"
            s += '  </atmosphere>\n'

        if self._flow_components:
            s += '  <flow name="%s">\n' % flowname
            for component in self._flow_components:
                s += component.toXML() + "\n"
            s += '  </flow>\n'

        s += '</planet>\n'

        return s
