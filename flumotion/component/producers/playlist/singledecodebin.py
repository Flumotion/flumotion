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

# Originally part of PiTiVi,
# Copyright (C) 2005-2007 Edward Hervey <bilboed@bilboed.com>,

"""
Single-stream queue-less decodebin
"""

import gobject
import gst

__version__ = "$Rev$"


def find_upstream_demuxer_and_pad(pad):
    while pad:
        if pad.props.direction == gst.PAD_SRC \
                and isinstance(pad, gst.GhostPad):
            pad = pad.get_target()
            continue

        if pad.props.direction == gst.PAD_SINK:
            pad = pad.get_peer()
            continue

        element = pad.get_parent()
        if isinstance(element, gst.Pad):
            # pad is a proxy pad
            element = element.get_parent()

        if element is None:
            pad = None
            continue

        element_factory = element.get_factory()
        element_klass = element_factory.get_klass()

        if 'Demuxer' in element_klass:
            return element, pad

        sink_pads = list(element.sink_pads())
        if len(sink_pads) > 1:
            if element_factory.get_name() == 'multiqueue':
                pad = element.get_pad(pad.get_name().replace('src', 'sink'))
            else:
                raise Exception('boom!')

        elif len(sink_pads) == 0:
            pad = None
        else:
            pad = sink_pads[0]

    return None, None


def get_type_from_decoder(decoder):
    klass = decoder.get_factory().get_klass()
    parts = klass.split('/', 2)
    if len(parts) != 3:
        return None

    return parts[2].lower()


def get_pad_id(pad):
    lst = []
    while pad:
        demuxer, pad = find_upstream_demuxer_and_pad(pad)
        if (demuxer, pad) != (None, None):
            lst.append([demuxer.get_factory().get_name(), pad.get_name()])

            # FIXME: we always follow back the first sink
            try:
                pad = list(demuxer.sink_pads())[0]
            except IndexError:
                pad = None

    return lst


def is_raw(caps):
    """ returns True if the caps are RAW """
    rep = caps.to_string()
    valid = ["video/x-raw", "audio/x-raw", "text/plain", "text/x-pango-markup"]
    for val in valid:
        if rep.startswith(val):
            return True
    return False


class SingleDecodeBin(gst.Bin):
    """
    A variant of decodebin.

    * Only outputs one stream
    * Doesn't contain any internal queue
    """

    QUEUE_SIZE = 1 * gst.SECOND

    __gsttemplates__ = (
        gst.PadTemplate("sinkpadtemplate", gst.PAD_SINK, gst.PAD_ALWAYS,
                         gst.caps_new_any()),
        gst.PadTemplate("srcpadtemplate", gst.PAD_SRC, gst.PAD_SOMETIMES,
                         gst.caps_new_any()))

    def __init__(self, caps=None, uri=None, stream=None, *args, **kwargs):
        gst.Bin.__init__(self, *args, **kwargs)

        if not caps:
            caps = gst.caps_new_any()
        self.caps = caps
        self.stream = stream
        self.typefind = gst.element_factory_make("typefind",
            "internal-typefind")
        self.add(self.typefind)

        self.uri = uri
        if self.uri and gst.uri_is_valid(self.uri):
            self.urisrc = gst.element_make_from_uri(gst.URI_SRC, uri, "urisrc")
            self.log("created urisrc %s / %r" % (self.urisrc.get_name(),
                                                 self.urisrc))
            self.add(self.urisrc)
            self.urisrc.link(self.typefind)
        else:
            self._sinkpad = gst.GhostPad("sink", self.typefind.get_pad("sink"))
            self._sinkpad.set_active(True)
            self.add_pad(self._sinkpad)

        self.typefind.connect("have_type", self._typefindHaveTypeCb)

        self._srcpad = None

        self._dynamics = []

        self._validelements = [] #added elements

        self._factories = self._getSortedFactoryList()


    ## internal methods

    def _controlDynamicElement(self, element):
        self.log("element:%s" % element.get_name())
        self._dynamics.append(element)
        element.connect("pad-added", self._dynamicPadAddedCb)
        element.connect("no-more-pads", self._dynamicNoMorePadsCb)

    def _getSortedFactoryList(self):
        """
        Returns the list of demuxers, decoders and parsers available, sorted
        by rank
        """

        def _myfilter(fact):
            if fact.get_rank() < 64:
                return False
            klass = fact.get_klass()
            if not ("Demuxer" in klass or "Decoder" in klass \
                or "Parse" in klass):
                return False
            return True
        reg = gst.registry_get_default()
        res = [x for x in reg.get_feature_list(gst.ElementFactory) \
            if _myfilter(x)]
        res.sort(lambda a, b: int(b.get_rank() - a.get_rank()))
        return res

    def _findCompatibleFactory(self, caps):
        """
        Returns a list of factories (sorted by rank) which can take caps as
        input. Returns empty list if none are compatible
        """
        self.debug("caps:%s" % caps.to_string())
        res = []
        for factory in self._factories:
            for template in factory.get_static_pad_templates():
                if template.direction == gst.PAD_SINK:
                    intersect = caps.intersect(template.static_caps.get())
                    if not intersect.is_empty():
                        res.append(factory)
                        break
        self.debug("returning %r" % res)
        return res

    def _closeLink(self, element):
        """
        Inspects element and tries to connect something on the srcpads.
        If there are dynamic pads, it sets up a signal handler to
        continue autoplugging when they become available.
        """
        to_connect = []
        dynamic = False
        templates = element.get_pad_template_list()
        for template in templates:
            if not template.direction == gst.PAD_SRC:
                continue
            if template.presence == gst.PAD_ALWAYS:
                pad = element.get_pad(template.name_template)
                to_connect.append(pad)
            elif template.presence == gst.PAD_SOMETIMES:
                pad = element.get_pad(template.name_template)
                if pad:
                    to_connect.append(pad)
                else:
                    dynamic = True
            else:
                self.log("Template %s is a request pad, ignoring" % (
                    pad.name_template))

        if dynamic:
            self.debug("%s is a dynamic element" % element.get_name())
            self._controlDynamicElement(element)

        for pad in to_connect:
            self._closePadLink(element, pad, pad.get_caps())

    def _isDemuxer(self, element):
        if not 'Demux' in element.get_factory().get_klass():
            return False

        potential_src_pads = 0
        for template in element.get_pad_template_list():
            if template.direction != gst.PAD_SRC:
                continue

            if template.presence == gst.PAD_REQUEST or \
                    "%" in template.name_template:
                potential_src_pads += 2
                break
            else:
                potential_src_pads += 1

        return potential_src_pads > 1

    def _plugDecodingQueue(self, pad):
        queue = gst.element_factory_make("queue")
        queue.props.max_size_time = self.QUEUE_SIZE
        self.add(queue)
        queue.sync_state_with_parent()
        pad.link(queue.get_pad("sink"))
        pad = queue.get_pad("src")

        return pad

    def _tryToLink1(self, source, pad, factories):
        """
        Tries to link one of the factories' element to the given pad.

        Returns the element that was successfully linked to the pad.
        """
        self.debug("source:%s, pad:%s , factories:%r" % (source.get_name(),
                                                         pad.get_name(),
                                                         factories))

        if self._isDemuxer(source):
            pad = self._plugDecodingQueue(pad)

        result = None
        for factory in factories:
            element = factory.create()
            if not element:
                self.warning("weren't able to create element from %r" % (
                    factory))
                continue

            sinkpad = element.get_pad("sink")
            if not sinkpad:
                continue

            self.add(element)
            element.set_state(gst.STATE_READY)
            try:
                pad.link(sinkpad)
            except:
                element.set_state(gst.STATE_NULL)
                self.remove(element)
                continue

            self._closeLink(element)
            element.set_state(gst.STATE_PAUSED)

            result = element
            break

        return result

    def _closePadLink(self, element, pad, caps):
        """
        Finds the list of elements that could connect to the pad.
        If the pad has the desired caps, it will create a ghostpad.
        If no compatible elements could be found, the search will stop.
        """
        self.debug("element:%s, pad:%s, caps:%s" % (element.get_name(),
                                                    pad.get_name(),
                                                    caps.to_string()))
        if caps.is_empty():
            self.log("unknown type")
            return
        if caps.is_any():
            self.log("type is not know yet, waiting")
            return

        if caps.intersect(self.caps) and (self.stream is None or
                (self.stream.pad_id == get_pad_id(pad))):
            # This is the desired caps
            if not self._srcpad:
                self._wrapUp(element, pad)
        elif is_raw(caps):
            self.log("We hit a raw caps which isn't the wanted one")
            # FIXME : recursively remove everything until demux/typefind

        else:
            # Find something
            if len(caps) > 1:
                self.log("many possible types, delaying")
                return
            facts = self._findCompatibleFactory(caps)
            if not facts:
                self.log("unknown type")
                return
            self._tryToLink1(element, pad, facts)

    def _wrapUp(self, element, pad):
        """
        Ghost the given pad of element.
        Remove non-used elements.
        """

        if self._srcpad:
            return
        self._markValidElements(element)
        self._removeUnusedElements(self.typefind)
        self.log("ghosting pad %s" % pad.get_name())
        self._srcpad = gst.GhostPad("src", pad)
        self._srcpad.set_active(True)
        self.add_pad(self._srcpad)
        self.post_message(gst.message_new_state_dirty(self))

    def _markValidElements(self, element):
        """
        Mark this element and upstreams as valid
        """
        self.log("element:%s" % element.get_name())
        if element == self.typefind:
            return
        self._validelements.append(element)
        # find upstream element
        pad = list(element.sink_pads())[0]
        parent = pad.get_peer().get_parent()
        self._markValidElements(parent)

    def _removeUnusedElements(self, element):
        """
        Remove unused elements connected to srcpad(s) of element
        """
        self.log("element:%r" % element)
        for pad in element.src_pads():
            if pad.is_linked():
                peer = pad.get_peer().get_parent()
                self._removeUnusedElements(peer)
                if not peer in self._validelements:
                    self.log("removing %s" % peer.get_name())
                    pad.unlink(pad.get_peer())
                    peer.set_state(gst.STATE_NULL)
                    self.remove(peer)

    def _cleanUp(self):
        self.log("")
        if self._srcpad:
            self.remove_pad(self._srcpad)
        self._srcpad = None
        for element in self._validelements:
            element.set_state(gst.STATE_NULL)
            self.remove(element)
        self._validelements = []

    ## Overrides

    def do_change_state(self, transition):
        self.debug("transition:%r" % transition)
        res = gst.Bin.do_change_state(self, transition)
        if transition == gst.STATE_CHANGE_PAUSED_TO_READY:
            self._cleanUp()
        return res

    ## Signal callbacks

    def _typefindHaveTypeCb(self, typefind, probability, caps):
        self.debug("probability:%d, caps:%s" % (probability, caps.to_string()))
        self._closePadLink(typefind, typefind.get_pad("src"), caps)

    ## Dynamic element Callbacks

    def _dynamicPadAddedCb(self, element, pad):
        self.log("element:%s, pad:%s" % (element.get_name(), pad.get_name()))
        if not self._srcpad:
            self._closePadLink(element, pad, pad.get_caps())

    def _dynamicNoMorePadsCb(self, element):
        self.log("element:%s" % element.get_name())

gobject.type_register(SingleDecodeBin)
