# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
Feed components, participating in the stream
"""

import gst
import gst.interfaces
import gobject

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.configure import configure
from flumotion.component import component as basecomponent
from flumotion.common import common, interfaces, errors, log, compat
from flumotion.common import gstreamer, pygobject

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

class FeedComponentMedium(basecomponent.BaseComponentMedium):
    """
    I am a component-side medium for a FeedComponent to interface with
    the manager-side ComponentAvatar.
    """
    __implements__ = interfaces.IComponentMedium,
    logCategory = 'basecomponentmedium'

    def __init__(self, component):
        """
        @param component: L{flumotion.component.feedcomponent.FeedComponent}
        """
        basecomponent.BaseComponentMedium.__init__(self, component)

        def on_feed_ready(component, feedName, isReady):
            self.callRemote('feedReady', feedName, isReady)

        def on_component_error(component, element_path, message):
            self.callRemote('error', element_path, message)

        self.comp.connect('feed-ready', on_feed_ready)
        self.comp.connect('error', on_component_error)
        
        # override base Errback for callRemote to stop the pipeline
        #def callRemoteErrback(reason):
        #    self.warning('stopping pipeline because of %s' % reason)
        #    self.comp.pipeline_stop()

    ### Referenceable remote methods which can be called from manager
    def remote_getElementProperty(self, elementName, property):
        return self.comp.get_element_property(elementName, property)
        
    def remote_setElementProperty(self, elementName, property, value):
        self.comp.set_element_property(elementName, property, value)

    def remote_provideMasterClock(self, port):
        """
        Tells the component to start providing a master clock on the given
        UDP port.
        Can only be called if setup() has been called on the component.

        @returns: (ip, port, base_time)
        @rtype:   tuple of (str, int, long)
        """
        self.debug('remote_provideMasterClock(port=%r)' % port)
        return self.comp.provide_master_clock(port)

    def remote_effect(self, effectName, methodName, *args, **kwargs):
        self.debug("calling %s on effect %s" % (methodName, effectName))
        if not effectName in self.comp.effects:
            raise errors.UnknownEffectError(effectName)
        effect = self.comp.effects[effectName]
        if not hasattr(effect, "effect_%s" % methodName):
            raise errors.NoMethodError("%s on effect %s" % (methodName,
                effectName))
        method = getattr(effect, "effect_%s" % methodName)
        try:
            result = method(*args, **kwargs)
        except TypeError:
            msg = "effect method %s did not accept %s and %s" % (
                methodName, args, kwargs)
            self.debug(msg)
            raise errors.RemoteRunError(msg)
        self.debug("effect: result: %r" % result)
        return result

if gst.gst_version < (0, 9):
    from feedcomponent08 import FeedComponent
else:
    from feedcomponent010 import FeedComponent

FeedComponent.component_medium_class = FeedComponentMedium

class ParseLaunchComponent(FeedComponent):
    'A component using gst-launch syntax'

    DELIMITER = '@'

    ### FeedComponent methods
    def create_pipeline(self):
        unparsed = self.get_pipeline_string(self.config['properties'])
        self.pipeline_string = self.parse_pipeline(unparsed)

        try:
            pipeline = gst.parse_launch(self.pipeline_string)
            return pipeline
        except gobject.GError, e:
            self.warning('Could not parse pipeline: %s' % e.message)
            raise errors.PipelineParseError(e.message)

    def set_pipeline(self, pipeline):
        FeedComponent.set_pipeline(self, pipeline)
        self.configure_pipeline(self.pipeline, self.config['properties'])

    ### ParseLaunchComponent methods
    def get_pipeline_string(self, properties):
        """
        Method that must be implemented by subclasses to produce the
        gstparse string for the component's pipeline. Subclasses should
        not chain up; this method raises a NotImplemented error.

        Returns: a new pipeline string representation.
        """
        raise NotImplementedError('subclasses should implement '
                                  'get_pipeline_string')
        
    def configure_pipeline(self, pipeline, properties):
        pass

    def _expandElementName(self, block):
        """
        Expand the given string to a full element name for an eater or feeder.
        The full name is of the form eater:(sourceComponentName):(feedName)
        or feeder:(componentName):feedName
        """
        if ' ' in block:
            raise TypeError, "spaces not allowed in '%s'" % block
        if not ':' in block:
            raise TypeError, "no colons in'%s'" % block
        if block.count(':') > 2:
            raise TypeError, "too many colons in '%s'" % block
            
        parts = block.split(':')

        if parts[0] != 'eater' and parts[0] != 'feeder':
            raise TypeError, "'%s' does not start with eater or feeder" % block
            
        # we can only fill in component names for feeders
        if not parts[1]:
            if parts[0] == 'eater':
                raise TypeError, "'%s' should specify feeder component" % block
            parts[1] = self.name
        if len(parts) == 2:
            parts.append('')
        if  not parts[2]:
            parts[2] = 'default'

        return ":".join(parts)
        
    def _expandElementNames(self, block):
        """
        Expand each @..@ block to use the full element name for eater or feeder.
        The full name is of the form eater:(sourceComponentName):(feedName)
        or feeder:(componentName):feedName
        This also does some basic checking of the block.
        """
        assert block != ''

        # verify the template has an even number of delimiters
        if block.count(self.DELIMITER) % 2 != 0:
            raise TypeError, "'%s' contains an odd number of '%s'" % (block, self.DELIMITER)
        
        # when splitting, the even-indexed members will remain,
        # and the odd-indexed members are the blocks to be substituted
        blocks = block.split(self.DELIMITER)

        for i in range(1, len(blocks) - 1, 2):
            blocks[i] = self._expandElementName(blocks[i].strip())
        return "@".join(blocks)
  
    def parse_tmpl(self, pipeline, names, template, format):
        """
        Expand the given pipeline string representation by substituting
        blocks between '@' with a filled-in template.

        @param pipeline: a pipeline string representation with variables
        @param names: the element names to substitute for @...@ segments
        @param template: the template to use for element factory info
        @param format: the format to use when substituting

        Returns: a new pipeline string representation.
        """
        assert pipeline != ''

        deli = self.DELIMITER

        if len(names) == 1:
            part_name = names[0]
            named = template % {'name': part_name}
            if pipeline.find(part_name) != -1:
                pipeline = pipeline.replace(deli + part_name + deli, named)
            else:
                pipeline = format % {'tmpl': named, 'pipeline': pipeline}
        else:
            for part in names:
                part_name = deli + part + deli # mmm, deli sandwich
                if pipeline.find(part_name) == -1:
                    raise TypeError, "%s needs to be specified in the pipeline '%s'" % (part_name, pipeline)
            
                pipeline = pipeline.replace(part_name,
                    template % {'name': part})
        return pipeline
        
    def parse_pipeline(self, pipeline):
        pipeline = " ".join(pipeline.split())
        self.debug('Creating pipeline, template is %s' % pipeline)
        
        eater_names = self.get_eater_names()
        if pipeline == '' and not eater_names:
            raise TypeError, "Need a pipeline or a eater"

        if pipeline == '':
            assert eater_names
            pipeline = 'fakesink signal-handoffs=1 silent=1 name=sink'
            
        # we expand the pipeline based on the templates and eater/feeder names
        # elements are named eater:(source_component_name):(feed_name)
        # or feeder:(component_name):(feed_name)
        eater_element_names = map(lambda n: "eater:" + n, eater_names)
        feeder_element_names = map(lambda n: "feeder:" + n, self.feeder_names)
        self.debug('we eat with eater elements %s' % eater_element_names)
        self.debug('we feed with feeder elements %s' % feeder_element_names)
        pipeline = self._expandElementNames(pipeline)
        
        pipeline = self.parse_tmpl(pipeline, eater_element_names,
                                   self.EATER_TMPL,
                                   '%(tmpl)s ! %(pipeline)s') 
        pipeline = self.parse_tmpl(pipeline, feeder_element_names,
                                   self.FEEDER_TMPL,
                                   '%(pipeline)s ! %(tmpl)s') 
        pipeline = " ".join(pipeline.split())
        
        self.debug('pipeline for %s is %s' % (self.getName(), pipeline))
        assert self.DELIMITER not in pipeline
        
        return pipeline

    # mood change/state vmethod impl
    def do_start(self, eatersData, feedersData, clocking):
        """
        Tell the component to start, linking itself to other components.

        @type eatersData:  list of (feedername, host, port) tuples of elements
                           feeding our eaters.
        @type feedersData: list of (name, host, port) tuples on which to
                           produce data.
        @param clocking: tuple of (ip, port, base_time) of a master clock,
                         or None not to slave the clock
        @type  clocking: tuple(str, int, long) or None.
        """
        self.debug('ParseLaunchComponent.start')
        self.debug('start with eaters data %s and feeders data %s' % (
            eatersData, feedersData))
        if clocking:
            self.info('slaving to clock on %s:%d with base time %d' % clocking)
        self.setMood(moods.waking)

        if clocking:
            self.set_master_clock(*clocking)

        self.link(eatersData, feedersData)


class Effect(log.Loggable):
    """
    I am a part of a feed component for a specific group
    of functionality.

    @ivar name:      name of the effect
    @type name:      string
    @ivar component: component owning the effect
    @type component: L{FeedComponent}
    """
    logCategory = "effect"

    def __init__(self, name):
        """
        @param name: the name of the effect
        """
        self.name = name
        self.component = None # component owning this effect

    def setComponent(self, component):
        """
        Set the given component as the effect's owner.
        
        @param component: the component to set as an owner of this effect
        @type  component: L{FeedComponent}
        """                               
        self.component = component

    def getComponent(self):
        """
        Get the component owning this effect.
        
        @rtype:  L{FeedComponent}
        """                               
        return self.component

