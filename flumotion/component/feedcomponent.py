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
Feed components, participating in the stream
"""

import gst
import gst.interfaces
import gobject

from twisted.internet import reactor, defer
from twisted.spread import pb

from flumotion.configure import configure
from flumotion.component import component as basecomponent
from flumotion.common import common, interfaces, errors, log, pygobject, messages
from flumotion.common import gstreamer

from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal
from flumotion.twisted.compat import implements

# FIXME: maybe move feed to component ?
from flumotion.worker import feed
from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class FeedComponentMedium(basecomponent.BaseComponentMedium):
    """
    I am a component-side medium for a FeedComponent to interface with
    the manager-side ComponentAvatar.
    """
    implements(interfaces.IComponentMedium)
    logCategory = 'feedcompmed'
    remoteLogName = 'feedserver'

    def __init__(self, component):
        """
        @param component: L{flumotion.component.feedcomponent.FeedComponent}
        """
        basecomponent.BaseComponentMedium.__init__(self, component)

        self._feederFeedServer = {} # FeedId -> (fullFeedId, host, port) tuple
                                    # for remote feeders
        self._feederClientFactory = {} # fullFeedId -> client factory
        self._eaterFeedServer = {}  # fullFeedId -> (host, port) tuple
                                    # for remote eaters
        self._eaterClientFactory = {} # (componentId, feedId) -> client factory
        self._eaterTransport = {}     # (componentId, feedId) -> transport
        self.logName = component.name

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

    def remote_eatFrom(self, fullFeedId, host, port):
        """
        Tell the component the host and port for the FeedServer through which
        it can connect a local eater to a remote feeder to eat the given
        fullFeedId.

        Called on by the manager-side ComponentAvatar.
        """
        # we key on the feedId because a component is part of only one flow,
        # and doesn't even know the flow name it is part of.
        flowName, componentName, feedName = common.parseFullFeedId(fullFeedId)
        feedId = common.feedId(componentName, feedName)
        self._feederFeedServer[feedId] = (fullFeedId, host, port)
        # FIXME: drop connection if we already had one
        return self.connectEater(feedId)

    def connectEater(self, feedId):
        """
        Actually eat the given feed.
        Used on initial connection, and for reconnecting.
        """
        (fullFeedId, host, port) = self._feederFeedServer[feedId]
        client = feed.FeedMedium(self.comp)
        factory = feed.FeedClientFactory(client)
        # FIXME: maybe copy keycard instead, so we can change requester ?
        self.debug('connecting to FeedServer on %s:%d' % (host, port))
        reactor.connectTCP(host, port, factory)
        d = factory.login(self.authenticator)
        self._feederClientFactory[fullFeedId] = factory
        def loginCb(remoteRef):
            self.debug('logged in to feedserver, remoteRef %r' % remoteRef)
            client.setRemoteReference(remoteRef)
            # now call on the remoteRef to eat
            self.debug(
                'COMPONENT --> feedserver: sendFeed(%s)' % fullFeedId)
            d = remoteRef.callRemote('sendFeed', fullFeedId)

            def sendFeedCb(result):
                self.debug('COMPONENT <-- feedserver: sendFeed(%s): %r' % (
                    fullFeedId, result))
                # FIXME: why does this not return result ?
                return None

            d.addCallback(sendFeedCb)
            return d

        d.addCallback(loginCb)
        return d

    def remote_feedTo(self, componentId, feedId, host, port):
        """
        Tell the component to feed the given feed to the receiving component
        accessible through the FeedServer on the given host and port.

        Called on by the manager-side ComponentAvatar.
        """
        # FIXME: check if this overwrites current config, and adapt if it
        # does
        self._eaterFeedServer[(componentId, feedId)] = (host, port)
        client = feed.FeedMedium(self.comp)
        factory = feed.FeedClientFactory(client)
        # FIXME: maybe copy keycard instead, so we can change requester ?
        self.debug('connecting to FeedServer on %s:%d' % (host, port))
        reactor.connectTCP(host, port, factory)
        d = factory.login(self.authenticator)
        self._eaterClientFactory[(componentId, feedId)] = factory
        def loginCb(remoteRef):
            self.debug('logged in to feedserver, remoteRef %r' % remoteRef)
            client.setRemoteReference(remoteRef)
            # now call on the remoteRef to eat
            self.debug(
                'COMPONENT --> feedserver: receiveFeed(%s, %s)' % (
                    componentId, feedId))
            d = remoteRef.callRemote('receiveFeed', componentId, feedId)

            def receiveFeedCb(result):
                self.debug(
                    'COMPONENT <-- feedserver: receiveFeed(%s, %s): %r' % (
                    componentId, feedId, result))
                componentName, feedName = common.parseFeedId(feedId)
                t = remoteRef.broker.transport
                t.stopReading()
                t.stopWriting()

                key = (componentId, feedId)
                self._eaterTransport[key] = t
                remoteRef.broker.transport = None
                fd = t.fileno()
                self.debug('Telling component to feed feedName %s to fd %d'% (
                    feedName, fd))
                self.comp.feedToFD(feedName, fd)
                
            d.addCallback(receiveFeedCb)
            return d

        d.addCallback(loginCb)
        return d

    def remote_provideMasterClock(self, port):
        """
        Tells the component to start providing a master clock on the given
        UDP port.
        Can only be called if setup() has been called on the component.

        The IP address returned is the local IP the clock is listening on.

        @returns: (ip, port, base_time)
        @rtype:   tuple of (str, int, long)
        """
        self.debug('remote_provideMasterClock(port=%r)' % port)
        return self.comp.provide_master_clock(port)

    def remote_effect(self, effectName, methodName, *args, **kwargs):
        """
        Invoke the given methodName on the given effectName in this component.
        The effect should implement effect_(methodName) to receive the call.
        """
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

from feedcomponent010 import FeedComponent

FeedComponent.componentMediumClass = FeedComponentMedium

class ParseLaunchComponent(FeedComponent):
    'A component using gst-launch syntax'

    DELIMITER = '@'

    ### FeedComponent interface implementations
    def create_pipeline(self):
        try:
            unparsed = self.get_pipeline_string(self.config['properties'])
        except errors.MissingElementError, e:
            m = messages.Error(T_(N_(
                "The worker does not have the '%s' element installed.\n"
                "Please install the necessary plug-in and restart "
                "the component.\n"), e.args[0]))
            self.state.append('messages', m)
            raise errors.ComponentSetupHandledError(e)
        
        self.pipeline_string = self.parse_pipeline(unparsed)

        try:
            pipeline = gst.parse_launch(self.pipeline_string)

            # Connect to the client-fd-removed signals on each feeder, so we 
            # can clean up properly on removal.
            feeder_element_names = map(lambda n: "feeder:" + n, 
                self.feeder_names)
            for feeder in feeder_element_names:
                element = pipeline.get_by_name(feeder)
                element.connect('client-fd-removed', self.removeClientCallback)
                self.debug("Connected %s to removeClientCallback", feeder)

            return pipeline
        except gobject.GError, e:
            self.warning('Could not parse pipeline: %s' % e.message)
            m = messages.Error(T_(N_(
                "GStreamer error: could not parse component pipeline.")),
                debug=e.message)
            self.state.append('messages', m)
            raise errors.PipelineParseError(e.message)

    def set_pipeline(self, pipeline):
        FeedComponent.set_pipeline(self, pipeline)
        self.configure_pipeline(self.pipeline, self.config['properties'])

    ### ParseLaunchComponent interface for subclasses
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
        """
        Method that can be implemented by subclasses if they wish to
        interact with the pipeline after it has been created and set
        on the component.

        This could include attaching signals and bus handlers.
        """
        pass

    ### private methods
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
  
    def parse_tmpl(self, pipeline, names, template_func, format):
        """
        Expand the given pipeline string representation by substituting
        blocks between '@' with a filled-in template.

        @param pipeline: a pipeline string representation with variables
        @param names: the element names to substitute for @...@ segments
        @param template_func: function to call to get the template to use for 
                              element factory info
        @param format: the format to use when substituting

        Returns: a new pipeline string representation.
        """
        assert pipeline != ''

        deli = self.DELIMITER

        if len(names) == 1:
            part_name = names[0]
            template = template_func(part_name)
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
            
                template = template_func(part)
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
                                   self.get_eater_template,
                                   '%(tmpl)s ! %(pipeline)s') 
        pipeline = self.parse_tmpl(pipeline, feeder_element_names,
                                   self.get_feeder_template,
                                   '%(pipeline)s ! %(tmpl)s') 
        pipeline = " ".join(pipeline.split())
        
        self.debug('pipeline for %s is %s' % (self.getName(), pipeline))
        assert self.DELIMITER not in pipeline
        
        return pipeline

    def get_eater_template(self, eaterName):
        queue = self.get_queue_string(eaterName)
        if not queue:
            return self.FDSRC_TMPL + ' ! ' + self.DEPAY_TMPL
        else:
            return self.FDSRC_TMPL + ' ! ' + queue  + ' ! ' + self.DEPAY_TMPL

    def get_feeder_template(self, eaterName):
        return self.FEEDER_TMPL

    def get_queue_string(self, eaterName):
        """
        Return a parse-launch description of a queue, if this component
        wants an input queue on this eater, or None if not
        """
        return None

    ### BaseComponent interface implementation
    def do_start(self, clocking):
        """
        Tell the component to start.
        Whatever is using the component is responsible for making sure all
        eaters have received their file descriptor to eat from.

        @param clocking: tuple of (ip, port, base_time) of a master clock,
                         or None not to slave the clock
        @type  clocking: tuple(str, int, long) or None.
        """
        self.debug('ParseLaunchComponent.start')
        if clocking:
            self.info('slaving to master clock on %s:%d with base time %d' %
                clocking)

        if clocking:
            self.set_master_clock(*clocking)

        self.link()

        return defer.succeed(None)

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
        self.setComponent(None)

    def setComponent(self, component):
        """
        Set the given component as the effect's owner.
        
        @param component: the component to set as an owner of this effect
        @type  component: L{FeedComponent}
        """                               
        self.component = component
        self.setUIState(component and component.uiState or None)

    def setUIState(self, state):
        """
        Set the given UI state on the effect. This method is ideal for
        adding keys to the UI state.
        
        @param state: the UI state for the component to use.
        @type  state: L{flumotion.common.componentui.WorkerComponentUIState}
        """                               
        self.uiState = state

    def getComponent(self):
        """
        Get the component owning this effect.
        
        @rtype:  L{FeedComponent}
        """                               
        return self.component

class MultiInputParseLaunchComponent(ParseLaunchComponent):
    """
    This class provides for multi-input ParseLaunchComponents, such as muxers,
    with a queue attached to each input.
    """
    QUEUE_SIZE_BUFFERS = 16

    def get_muxer_string(self, properties):
        """
        Return a gst-parse description of the muxer, which must be named 'muxer'
        """
        raise errors.NotImplementedError("Implement in a subclass")

    def get_queue_string(self, eaterName):
        return "queue name=%s-queue max-size-buffers=%d" % (eaterName, 
            self.QUEUE_SIZE_BUFFERS)

    def get_pipeline_string(self, properties):
        sources = self.config['source']

        pipeline = self.get_muxer_string(properties) + ' '
        for eater in sources:
            tmpl = '@ eater:%s @ ! muxer. '
            pipeline += tmpl % eater

        pipeline += 'muxer.'

        return pipeline

    def unblock_eater(self, feedId):
        # Firstly, ensure that any push in progress is guaranteed to return,
        # by temporarily enlarging the queue
        queuename = "eater:%s-queue" % feedId
        queue = self.pipeline.get_by_name(queuename)

        size = queue.get_property("max-size-buffers")
        queue.set_property("max-size-buffers", size + 1)

        # So, now it's guaranteed to return. However, we want to return the 
        # queue size to its original value. Doing this in a thread-safe manner
        # is rather tricky...
        def _block_cb(pad, blocked):
            # This is called from streaming threads, but we don't do anything
            # here so it's safe.
            pass
        def _underrun_cb(element):
            # Called from a streaming thread. The queue element does not hold
            # the queue lock when this is called, so we block our sinkpad, 
            # then re-check the current level.
            pad = element.get_pad("sink")
            pad.set_blocked_async(True, _block_cb)
            level = element.get_property("current-level-buffers")
            if level < self.QUEUE_SIZE_BUFFERS:
                element.set_property('max-size-buffers', 
                    self.QUEUE_SIZE_BUFFERS)
                element.disconnect(signalid)
            pad.set_blocked_async(False, _block_cb)

        signalid = queue.connect("underrun", _underrun_cb)


