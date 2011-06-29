# -*- Mode: Python -*-
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

"""
Feed components, participating in the stream
"""

import os

import gst
import gst.interfaces
import gobject

from twisted.internet import reactor, defer
from twisted.spread import pb
from zope.interface import implements

from flumotion.component import component as basecomponent
from flumotion.component import feed
from flumotion.common import common, interfaces, errors, log, pygobject, \
     messages
from flumotion.common import gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal

__version__ = "$Rev$"
T_ = gettexter()


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

        self._feederFeedServer = {} # eaterAlias -> (fullFeedId, host, port)
                                    # tuple for remote feeders
        self._feederPendingConnections = {} # eaterAlias -> cancel thunk
        self._eaterFeedServer = {}  # fullFeedId -> (host, port) tuple
                                    # for remote eaters
        self._eaterPendingConnections = {} # feederName -> cancel thunk
        self.logName = component.name

    ### Referenceable remote methods which can be called from manager

    def remote_attachPadMonitorToFeeder(self, feederName):
        self.comp.attachPadMonitorToFeeder(feederName)

    def remote_setGstDebug(self, debug):
        """
        Sets the GStreamer debugging levels based on the passed debug string.

        @since: 0.4.2
        """
        self.debug('Setting GStreamer debug level to %s' % debug)
        if not debug:
            return

        for part in debug.split(','):
            glob = None
            value = None
            pair = part.split(':')
            if len(pair) == 1:
                # assume only the value
                value = int(pair[0])
            elif len(pair) == 2:
                glob, value = pair
                value = int(value)
            else:
                self.warning("Cannot parse GStreamer debug setting '%s'." %
                    part)
                continue

            if glob:
                try:
                    # value has to be an integer
                    gst.debug_set_threshold_for_name(glob, value)
                except TypeError:
                    self.warning("Cannot set glob %s to value %s" % (
                        glob, value))
            else:
                gst.debug_set_default_threshold(value)

        self.comp.uiState.set('gst-debug', debug)

    def remote_eatFrom(self, eaterAlias, fullFeedId, host, port):
        """
        Tell the component the host and port for the FeedServer through which
        it can connect a local eater to a remote feeder to eat the given
        fullFeedId.

        Called on by the manager-side ComponentAvatar.
        """
        if self._feederFeedServer.get(eaterAlias):
            if self._feederFeedServer[eaterAlias] == (fullFeedId, host, port):
                self.debug("Feed:%r is the same as the current one. "\
                           "Request ignored.", (fullFeedId, host, port))
                return
        self._feederFeedServer[eaterAlias] = (fullFeedId, host, port)
        return self.connectEater(eaterAlias)

    def _getAuthenticatorForFeed(self, eaterAliasOrFeedName):
        # The avatarId on the keycards issued by the authenticator will
        # identify us to the remote component. Attempt to use our
        # fullFeedId, for debugging porpoises.
        if hasattr(self.authenticator, 'copy'):
            tup = common.parseComponentId(self.authenticator.avatarId)
            flowName, componentName = tup
            fullFeedId = common.fullFeedId(flowName, componentName,
                                           eaterAliasOrFeedName)
            return self.authenticator.copy(fullFeedId)
        else:
            return self.authenticator

    def connectEater(self, eaterAlias):
        """
        Connect one of the medium's component's eaters to a remote feed.
        Called by the component, both on initial connection and for
        reconnecting.

        @returns: deferred that will fire with a value of None
        """
        # FIXME: There's no indication if the connection was made or not

        def gotFeed((feedId, fd)):
            self._feederPendingConnections.pop(eaterAlias, None)
            self.comp.eatFromFD(eaterAlias, feedId, fd)

        if eaterAlias not in self._feederFeedServer:
            self.debug("eatFrom() hasn't been called yet for eater %s",
                       eaterAlias)
            # unclear if this function should have a return value at
            # all...
            return defer.succeed(None)

        (fullFeedId, host, port) = self._feederFeedServer[eaterAlias]

        cancel = self._feederPendingConnections.pop(eaterAlias, None)
        if cancel:
            self.debug('cancelling previous connection attempt on %s',
                       eaterAlias)
            cancel()

        client = feed.FeedMedium(logName=self.comp.name)

        d = client.requestFeed(host, port,
                               self._getAuthenticatorForFeed(eaterAlias),
                               fullFeedId)
        self._feederPendingConnections[eaterAlias] = client.stopConnecting
        d.addCallback(gotFeed)
        return d

    def remote_feedTo(self, feederName, fullFeedId, host, port):
        """
        Tell the component to feed the given feed to the receiving component
        accessible through the FeedServer on the given host and port.

        Called on by the manager-side ComponentAvatar.
        """
        self._eaterFeedServer[fullFeedId] = (host, port)
        self.connectFeeder(feederName, fullFeedId)

    def connectFeeder(self, feederName, fullFeedId):
        """
        Tell the component to feed the given feed to the receiving component
        accessible through the FeedServer on the given host and port.

        Called on by the manager-side ComponentAvatar.
        """

        def gotFeed((fullFeedId, fd)):
            self._eaterPendingConnections.pop(feederName, None)
            self.comp.feedToFD(feederName, fd, os.close, fullFeedId)

        if fullFeedId not in self._eaterFeedServer:
            self.debug("feedTo() hasn't been called yet for feeder %s",
                       feederName)
            # unclear if this function should have a return value at
            # all...
            return defer.succeed(None)

        host, port = self._eaterFeedServer[fullFeedId]

        # probably should key on feederName as well
        cancel = self._eaterPendingConnections.pop(fullFeedId, None)
        if cancel:
            self.debug('cancelling previous connection attempt on %s',
                       feederName)
            cancel()

        client = feed.FeedMedium(logName=self.comp.name)

        d = client.sendFeed(host, port,
                            self._getAuthenticatorForFeed(feederName),
                            fullFeedId)
        self._eaterPendingConnections[feederName] = client.stopConnecting
        d.addCallback(gotFeed)
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

    def remote_getMasterClockInfo(self):
        """
        Return the clock master info created by a previous call
        to provideMasterClock.

        @returns: (ip, port, base_time)
        @rtype:   tuple of (str, int, long)
        """
        return self.comp.get_master_clock()

    def remote_setMasterClock(self, ip, port, base_time):
        return self.comp.set_master_clock(ip, port, base_time)

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

    def remote_dumpGstreamerDotFile(self, filename):
        self.comp.dump_gstreamer_debug_dot_file(filename)

from feedcomponent010 import FeedComponent

FeedComponent.componentMediumClass = FeedComponentMedium


class ParseLaunchComponent(FeedComponent):
    """A component using gst-launch syntax

    @cvar checkTimestamp: whether to check continuity of timestamps for eaters
    @cvar checkOffset:    whether to check continuity of offsets for
    eaters
    """

    DELIMITER = '@'

    # can be set by subclasses
    checkTimestamp = False
    checkOffset = False

    # keep these as class variables for the tests
    FDSRC_TMPL = 'fdsrc name=%(name)s'
    DEPAY_TMPL = 'gdpdepay name=%(name)s-depay'
    FEEDER_TMPL = 'gdppay name=%(name)s-pay ! multifdsink sync=false '\
                      'name=%(name)s buffers-max=500 buffers-soft-max=450 '\
                      'recover-policy=1'
    EATER_TMPL = None

    def init(self):
        if not gstreamer.get_plugin_version('coreelements'):
            raise errors.MissingElementError('identity')
        if not gstreamer.element_factory_has_property('identity',
            'check-imperfect-timestamp'):
            self.checkTimestamp = False
            self.checkOffset = False
            self.addMessage(
                messages.Info(T_(N_(
                    "You will get more debugging information "
                    "if you upgrade to GStreamer 0.10.13 or later."))))

        self.EATER_TMPL = self.FDSRC_TMPL + ' %(queue)s ' + self.DEPAY_TMPL
        if self.checkTimestamp or self.checkOffset:
            self.EATER_TMPL += " ! identity name=%(name)s-identity silent=TRUE"
        if self.checkTimestamp:
            self.EATER_TMPL += " check-imperfect-timestamp=1"
        if self.checkOffset:
            self.EATER_TMPL += " check-imperfect-offset=1"

    ### FeedComponent interface implementations

    def create_pipeline(self):
        try:
            unparsed = self.get_pipeline_string(self.config['properties'])
        except errors.MissingElementError, e:
            self.warning('Missing %s element' % e.args[0])
            m = messages.Error(T_(N_(
                "The worker does not have the '%s' element installed.\n"
                "Please install the necessary plug-in and restart "
                "the component.\n"), e.args[0]))
            self.addMessage(m)
            raise errors.ComponentSetupHandledError(e)

        self.pipeline_string = self.parse_pipeline(unparsed)

        try:
            pipeline = gst.parse_launch(self.pipeline_string)
        except gobject.GError, e:
            self.warning('Could not parse pipeline: %s' % e.message)
            m = messages.Error(T_(N_(
                "GStreamer error: could not parse component pipeline.")),
                debug="Reason: %s\nPipeline: %s" % (
                    e.message, self.pipeline_string))
            self.addMessage(m)
            raise errors.PipelineParseError(e.message)

        return pipeline

    def set_pipeline(self, pipeline):
        FeedComponent.set_pipeline(self, pipeline)
        if self.checkTimestamp or self.checkOffset:
            watchElements = dict([
                (e.elementName + '-identity', e)
                for e in self.eaters.values()])
            self.install_eater_continuity_watch(watchElements)
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

    def add_default_eater_feeder(self, pipeline):
        if len(self.eaters) == 1:
            eater = 'eater:' + self.eaters.keys()[0]
            if eater not in pipeline:
                pipeline = '@' + eater + '@ ! ' + pipeline
        if len(self.feeders) == 1:
            feeder = 'feeder:' + self.feeders.keys()[0]
            if feeder not in pipeline:
                pipeline = pipeline + ' ! @' + feeder + '@'
        return pipeline

    def parse_tmpl(self, pipeline, templatizers):
        """
        Expand the given pipeline string representation by substituting
        blocks between '@' with a filled-in template.

        @param pipeline: a pipeline string representation with variables
        @param templatizers: A dict of prefix => procedure. Template
                             blocks in the pipeline will be replaced
                             with the result of calling the procedure
                             with what is left of the template after
                             taking off the prefix.
        @returns: a new pipeline string representation.
        """
        assert pipeline != ''

        # verify the template has an even number of delimiters
        if pipeline.count(self.DELIMITER) % 2 != 0:
            raise TypeError("'%s' contains an odd number of '%s'"
                            % (pipeline, self.DELIMITER))

        out = []
        for i, block in enumerate(pipeline.split(self.DELIMITER)):
            # when splitting, the even-indexed members will remain, and
            # the odd-indexed members are the blocks to be substituted
            if i % 2 == 0:
                out.append(block)
            else:
                block = block.strip()
                try:
                    pos = block.index(':')
                except ValueError:
                    raise TypeError("Template %r has no colon" % (block, ))
                prefix = block[:pos+1]
                if prefix not in templatizers:
                    raise TypeError("Template %r has invalid prefix %r"
                                    % (block, prefix))
                out.append(templatizers[prefix](block[pos+1:]))
        return ''.join(out)

    def parse_pipeline(self, pipeline):
        """
        Parse the pipeline template into a fully expanded pipeline string.

        @type  pipeline: str

        @rtype: str
        """
        pipeline = " ".join(pipeline.split())
        self.debug('Creating pipeline, template is %s', pipeline)

        if pipeline == '' and not self.eaters:
            raise TypeError("Need a pipeline or a eater")

        if pipeline == '':
            # code of dubious value
            assert self.eaters
            pipeline = 'fakesink signal-handoffs=1 silent=1 name=sink'

        pipeline = self.add_default_eater_feeder(pipeline)
        pipeline = self.parse_tmpl(pipeline,
                                   {'eater:': self.get_eater_template,
                                    'feeder:': self.get_feeder_template})

        self.debug('pipeline is %s', pipeline)
        assert self.DELIMITER not in pipeline

        return pipeline

    def get_eater_template(self, eaterAlias):
        queue = self.get_queue_string(eaterAlias)
        elementName = self.eaters[eaterAlias].elementName

        return self.EATER_TMPL % {'name': elementName, 'queue': queue}

    def get_feeder_template(self, feederName):
        elementName = self.feeders[feederName].elementName
        return self.FEEDER_TMPL % {'name': elementName}

    def get_queue_string(self, eaterAlias):
        """
        Return a parse-launch string to join the fdsrc eater element and
        the depayer, for example '!' or '! queue !'. The string may have
        no format strings.
        """
        return '!'

    def get_eater_srcpad(self, eaterAlias):
        """
        Method that returns the source pad of the final element in an eater.

        @returns:   the GStreamer source pad of the final element in an eater
        @rtype:     L{gst.Pad}
        """
        e = self.eaters[eaterAlias]
        identity = self.get_element(e.elementName + '-identity')
        depay = self.get_element(e.depayName)
        srcpad = depay.get_pad("src")
        if identity:
            srcpad = identity.get_pad("src")
        return srcpad

    def get_feeder_sinkpad(self, feederAlias):
        """
        Method that returns the sink pad of the first element in a feeder

        @returns:   the GStreamer sink pad of the first element in a feeder
        @rtype:     L{gst.Pad}
        """
        e = self.feeders[feederAlias]
        gdppay = self.get_element(e.elementName + '-pay')
        return gdppay.get_static_pad("sink")


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


class PostProcEffect (Effect):
    """
    I am an effect that is plugged in the pipeline to do a post processing
    job and can be chained to other effect of the same class.

    @ivar name:      name of the effect
    @type name:      string
    @ivar component: component owning the effect
    @type component: L{FeedComponent}
    @ivar sourcePad: pad of the source after which I'm plugged
    @type sourcePad: L{GstPad}
    @ivar effectBin: gstreamer bin doing the post processing effect
    @type source:    L{GstBin}
    @ivar pipeline:  pipeline holding the gstreamer elements
    @type pipeline:  L{GstPipeline}

    """
    logCategory = "effect"

    def __init__(self, name, sourcePad, effectBin, pipeline):
        """
        @param name:      the name of the effect
        @param sourcePad: pad of the source after which I'm plugged
        @param effectBin: gstreamer bin doing the post processing effect
        @param pipeline:  pipeline holding the gstreamer elements
        """
        Effect.__init__(self, name)
        self.sourcePad = sourcePad
        self.effectBin = effectBin
        self.pipeline = pipeline
        self.plugged = False

    def plug(self):
        """
        Plug the effect in the pipeline unlinking the source element with it's
        downstream peer
        """
        if self.plugged:
            return
        # Unlink the source pad of the source element after which we need
        # are going to be plugged
        peerSinkPad = self.sourcePad
        peerSrcPad = peerSinkPad.get_peer()
        peerSinkPad.unlink(peerSrcPad)

        # Add the deinterlacer bin to the pipeline
        self.effectBin.set_state(gst.STATE_PLAYING)
        self.pipeline.add(self.effectBin)

        # link it with the element src pad and its peer's sink pad
        peerSinkPad.link(self.effectBin.get_pad('sink'))
        self.effectBin.get_pad('src').link(peerSrcPad)
        self.plugged = True


class MultiInputParseLaunchComponent(ParseLaunchComponent):
    """
    This class provides for multi-input ParseLaunchComponents, such as muxers,
    with a queue attached to each input.
    """
    QUEUE_SIZE_BUFFERS = 16
    LINK_MUXER = True

    def get_muxer_string(self, properties):
        """
        Return a gst-parse description of the muxer, which
        must be named 'muxer'
        """
        raise errors.NotImplementedError("Implement in a subclass")

    def get_queue_string(self, eaterAlias):
        name = self.eaters[eaterAlias].elementName
        return ("! queue name=%s-queue max-size-buffers=%d !"
                % (name, self.QUEUE_SIZE_BUFFERS))

    def get_pipeline_string(self, properties):
        eaters = self.config.get('eater', {})
        sources = self.config.get('source', [])
        if eaters == {} and sources != []:
            # for upgrade without manager restart
            feeds = []
            for feed in sources:
                if not ':' in feed:
                    feed = '%s:default' % feed
                feeds.append(feed)
            eaters = {'default': [(x, 'default') for x in feeds]}

        pipeline = ''
        for e in eaters:
            for feed, alias in eaters[e]:
                pipeline += '@ eater:%s @ ' % alias
                if self.LINK_MUXER:
                    pipeline += ' ! muxer. '

        pipeline += self.get_muxer_string(properties) + ' '

        return pipeline

    def unblock_eater(self, eaterAlias):
        # Firstly, ensure that any push in progress is guaranteed to return,
        # by temporarily enlarging the queue
        queuename = self.eaters[eaterAlias].elementName + '-queue'
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


class ReconfigurableComponent(ParseLaunchComponent):

    disconnectedPads = False
    dropStreamHeaders = False

    def _get_base_pipeline_string(self):
        """Should be overrided by subclasses to provide the pipeline the
        component uses.
        """
        return ""

    def init(self):
        self.EATER_TMPL += ' ! queue name=input-%(name)s'
        self._reset_count = 0

        self.uiState.addKey('reset-count', 0)
        self.not_dropping = False

    def setup_completed(self):
        ParseLaunchComponent.setup_completed(self)
        self._install_changes_probes()

    # Public methods

    def get_output_elements(self):
        return [self.get_element(f.elementName + '-pay')
                for f in self.feeders.values()]

    def get_input_elements(self):
        return [self.get_element('input-' + f.elementName)
                for f in self.eaters.values()]

    def get_base_pipeline_string(self):
        raise NotImplementedError('Subclasses should implement '
                                  'get_base_pipeline_string')

    def get_eater_srcpad(self, eaterAlias):
        e = self.eaters[eaterAlias]
        inputq = self.get_element('input-' + e.elementName)
        return inputq.get_pad('src')

    # Private methods

    def _install_changes_probes(self):
        """
        Add the event probes that will check for a caps change.

        Those will trigger the pipeline's blocking and posterior reload
        """
        # FIXME: Add documentation

        def output_reset_event(pad, event):
            if event.type != gst.EVENT_FLUSH_START:
                return True

            self.debug('RESET: out reset event received on output pad %r', pad)
            # TODO: Can we use EVENT_FLUSH_{START,STOP} for the same purpose?
            # The component only waits for the first eos to come. After that
            # all the elements inside the pipeline will be down and won't
            # process any more events.
            # Pads cannot be blocked from the streaming thread. They have to be
            # manipulated from outside according gstreamer's documentation
            self._reset_count -= 1
            if self._reset_count > 0:
                return False

            reactor.callFromThread(self._on_pipeline_drained)
            # Do not let the eos pass.
            return False

        def got_new_caps(pad, args):
            caps = pad.get_negotiated_caps()
            if not caps:
                self.debug("RESET: Caps unset! Looks like we're stopping")
                return
            self.debug("Got new caps at %s: %s",
                      pad.get_name(), caps.to_string())

            if self.disconnectedPads:
                return

            # FIXME: Only reset when the caps change and prevent the headers to
            # propagate when they are the same
            #if not self._capsChanged(caps):
            #    return

            self.debug('RESET: caps changed on input pad %r', pad)
            self._reset_count = len(self.feeders)
            # Block all the eaters and send an eos downstream the pipeline to
            # drain all the elements. It will also unlink the pipeline from the
            # input queues.
            self._block_eaters()

        def got_new_buffer(pad, buff, element):
            if self.disconnectedPads:
                self.info("INCAPS: Got buffer but we're still disconnected.")
                return True

            if not buff.flag_is_set(gst.BUFFER_FLAG_IN_CAPS):
                self.not_dropping = False
                return True

            self.info("INCAPS: Got buffer with caps of len %d", buff.size)
            peer = pad.get_peer()
            oldcaps = peer.get_negotiated_caps()
            newcaps = buff.caps
            self.info("INCAPS: Old caps are: %s", oldcaps and oldcaps.to_string() or "NONE")
            self.info("INCAPS: NEw caps are: %s", newcaps and newcaps.to_string() or "NONE")
            if oldcaps and newcaps.is_equal(oldcaps) and not self.not_dropping:
                self.info("INCAPS: Got same caps as before, dropping")
                return False
            self.not_dropping = True
            return True

        self.log('RESET: installing event probes for detecting changes')
        # Listen for incoming flumotion-reset events on eaters
        for elem in self.get_input_elements():
            self.debug('RESET: Add caps monitor for %s', elem.get_name())
            sink = elem.get_pad('sink')
            sink.get_peer().add_buffer_probe(got_new_buffer, elem)
            sink.connect("notify::caps", got_new_caps)

        for elem in self.get_output_elements():
            self.debug('RESET: adding event probe for %s', elem.get_name())
            elem.get_pad('sink').add_event_probe(output_reset_event)

    def _block_eaters(self):
        """
        Function that blocks all the identities of the eaters
        """
        for elem in self.get_input_elements():
            pad = elem.get_pad('src')
            self.debug("RESET: Blocking pad %s", pad)
            pad.set_blocked_async(True, self._on_eater_blocked)

    def _unblock_eaters(self):
        for elem in self.get_input_elements():
            pad = elem.get_pad('src')
            self.debug("RESET: Unblocking pad %s", pad)
            pad.set_blocked_async(False, self._on_eater_blocked)

    def _unlink_pads(self, element, directions):
        for pad in element.pads():
            ppad = pad.get_peer()
            if not ppad:
                continue
            if (pad.get_direction() in directions and
                pad.get_direction() == gst.PAD_SINK):
                self.debug('RESET: unlink %s with %s', pad, ppad)
                ppad.unlink(pad)
            elif (pad.get_direction() in directions and
                  pad.get_direction() == gst.PAD_SRC):
                self.debug('RESET: unlink %s with %s', pad, ppad)
                pad.unlink(ppad)

    def _remove_pipeline(self, pipeline, element, end, done=None):
            if done is None:
                done = []
            if not element:
                return
            if element in done:
                return
            if element in end:
                return

            for src in element.src_pads():
                self.log('going to start by pad %r', src)
                if not src.get_peer():
                    continue
                peer = src.get_peer().get_parent()
                self._remove_pipeline(pipeline, peer, end, done)
                done.append(peer)
                element.unlink(peer)

            self.log("RESET: removing old element %s from pipeline", element)
            element.set_state(gst.STATE_NULL)
            pipeline.remove(element)

    def _rebuild_pipeline(self):
        # TODO: Probably this would be easier and clearer if we used a bin to
        # wrap the component's functionality.Then the component would only need
        # to reset the bin and connect the resulting pads to the {eat,feed}ers.

        self.log('RESET: Going to rebuild the pipeline')

        base_pipe = self._get_base_pipeline_string()

        # Place a fakesrc element so we can know from where to start
        # rebuilding the pipeline.
        fake_pipeline = 'fakesrc name=start ! %s' % base_pipe
        pipeline = gst.parse_launch(fake_pipeline)

        def move_element(element, orig, dest):
            if not element:
                return
            if element in done:
                return

            to_link = []
            done.append(element)
            self.log("RESET: going to remove %s", element)
            for src in element.src_pads():
                self.log("RESET: got src pad element %s", src)
                if not src.get_peer():
                    continue
                peer = src.get_peer().get_parent()
                to_link.append(peer)

                move_element(to_link[-1], orig, dest)

            self._unlink_pads(element, [gst.PAD_SRC, gst.PAD_SINK])
            orig.remove(element)
            dest.add(element)

            self.log("RESET: new element %s added to the pipeline", element)
            for peer in to_link:
                self.log("RESET: linking peers %s -> %s", element, peer)
                element.link(peer)

        done = []
        start = pipeline.get_by_name('start').get_pad('src').get_peer()
        move_element(start.get_parent(), pipeline, self.pipeline)

        # Link eaters to the first element in the pipeline
        # By now we there can only be two situations:
        # 1. Encoders, where there is only one eater connected to the encoder
        # 2. Muxers, where multiple eaters are connected directly to the muxer
        # TODO: Probably we'd like the link process to check the caps
        if len(self.get_input_elements()) == 1:
            elem = self.get_input_elements()[0]
            self.log("RESET: linking eater %r to %r", elem, done[0])
            elem.link(done[0])

        # Link the last element in the pipeline to the feeders.
        if len(self.get_output_elements()) == 1:
            elem = self.get_output_elements()[0]
            self.log("RESET: linking %r to feeder %r", done[-1], elem)
            done[-1].link(elem)

        self.configure_pipeline(self.pipeline, self.config['properties'])
        self.pipeline.set_state(gst.STATE_PLAYING)
        self._unblock_eaters()

        resets = self.uiState.get('reset-count')
        self.uiState.set('reset-count', resets+1)

    # Callbacks

    def _on_pad_blocked(self, pad, blocked):
        self.log("RESET: Pad %s %s", pad,
                 (blocked and "blocked") or "unblocked")

    def _on_eater_blocked(self, pad, blocked):
        self._on_pad_blocked(pad, blocked)
        if blocked:
            peer = pad.get_peer()
            peer.send_event(gst.event_new_flush_start())
            #peer.send_event(gst.event_new_eos())
            #self._unlink_pads(pad.get_parent(), [gst.PAD_SRC])

    def _on_pipeline_drained(self):
        self.debug('RESET: Proceed to unlink pipeline')
        start = self.get_input_elements()
        end = self.get_output_elements()
        done = []
        for element in start:
            element = element.get_pad('src').get_peer().get_parent()
            self._remove_pipeline(self.pipeline, element, end, done)
        self._rebuild_pipeline()


class EncoderComponent(ParseLaunchComponent):
    """
    Component that is reconfigured when new changes arrive through the
    flumotion-reset event (sent by the fms producer).
    """
    pass


class MuxerComponent(MultiInputParseLaunchComponent):
    """
    This class provides for multi-input ParseLaunchComponents, such as muxers,
    that handle flumotion-reset events for reconfiguration.
    """

    LINK_MUXER = False
    dropAudioKuEvents = True

    def get_link_pad(self, muxer, srcpad, caps):
        return muxer.get_compatible_pad(srcpad, caps)

    def buffer_probe_cb(self, pad, buffer, depay, eaterAlias):
        pad = depay.get_pad("src")
        caps = pad.get_negotiated_caps()
        if not caps:
            return False
        srcpad_to_link = self.get_eater_srcpad(eaterAlias)
        muxer = self.pipeline.get_by_name("muxer")
        self.debug("Trying to get compatible pad for pad %r with caps %s",
            srcpad_to_link, caps)
        linkpad = self.get_link_pad(muxer, srcpad_to_link, caps)
        if not linkpad:
            m = messages.Error(T_(N_(
                "The incoming data is not compatible with this muxer.")),
                debug="Caps %s not compatible with this muxer." % (
                    caps.to_string()))
            self.addMessage(m)
            # this is the streaming thread, cannot set state here
            # so we do it in the mainloop
            reactor.callLater(0, self.pipeline.set_state, gst.STATE_NULL)
            return True
        self.debug("Got link pad %r", linkpad)
        srcpad_to_link.link(linkpad)
        depay.get_pad("src").remove_buffer_probe(self._probes[eaterAlias])
        if srcpad_to_link.is_blocked():
            self.is_blocked_cb(srcpad_to_link, True)
        else:
            srcpad_to_link.set_blocked_async(True, self.is_blocked_cb)
        return True

    def event_probe_cb(self, pad, event, depay, eaterAlias):
        caps = pad.get_negotiated_caps()
        if caps is None:
            return True
        # if this pad doesn't push audio, remove the probe
        if 'audio' not in caps[0].to_string():
            depay.get_pad("src").remove_buffer_probe(self._eprobes[eaterAlias])
        if event.get_structure().get_name() == 'GstForceKeyUnit':
            return False
        return True

    def configure_pipeline(self, pipeline, properties):
        """
        Method not overridable by muxer subclasses.
        """
        # link the muxers' sink pads when data comes in so we get compatible
        # sink pads with input data
        # gone are the days when we know we only have one pad template in
        # muxers
        self.fired_eaters = 0
        self._probes = {} # depay element -> id
        self._eprobes = {} # depay element -> id

        for e in self.eaters:
            depay = self.get_element(self.eaters[e].depayName)
            self._probes[e] = \
                depay.get_pad("src").add_buffer_probe(
                    self.buffer_probe_cb, depay, e)
            # Add an event probe to drop GstForceKeyUnit events
            # in audio pads
            if self.dropAudioKuEvents:
                self._eprobes[e] = \
                    depay.get_pad("src").add_event_probe(
                        self.event_probe_cb, depay, e)

    def is_blocked_cb(self, pad, is_blocked):
        if is_blocked:
            self.fired_eaters = self.fired_eaters + 1
            if self.fired_eaters == len(self.eaters):
                self.debug("All pads are now blocked")
                self.disconnectedPads = False
                for e in self.eaters:
                    srcpad = self.get_eater_srcpad(e)
                    srcpad.set_blocked_async(False, self.is_blocked_cb)
