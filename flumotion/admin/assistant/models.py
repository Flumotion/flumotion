# -*- Mode: Python; test-case-name: flumotion.test.test_wizard_models -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""model objects used by the configuration assistant steps"""

import random

from flumotion.common import log
from flumotion.common.errors import ComponentValidationError
from flumotion.common.fraction import fractionFromValue

__version__ = "$Rev$"


def _generateRandomString(numchars):
    """Generate a random US-ASCII string of length numchars
    """
    s = ""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    for unused in range(numchars):
        s += chars[random.randint(0, len(chars)-1)]

    return s


class Properties(dict):
    """I am a special dictionary which you also can treat as an instance.
    Setting and getting an attribute works.
    This is suitable for using in a kiwi proxy.
    >>> p = Properties()
    >>> p.attr = 'value'
    >>> p
    <Properties {'attr': 'value'}>

    Note that you cannot insert the attributes which has the same name
    as dictionary methods, such as 'keys', 'values', 'items', 'update'.

    Underscores are converted to dashes when setting attributes, eg:

    >>> p.this_is_outrageous = True
    >>> p
    <Properties {'this-is-outrageous': True}>
    """

    def __setitem__(self, attr, value):
        if attr in dict.__dict__:
            raise AttributeError(
                "Cannot set property %r, it's a dictionary attribute"
                % (attr, ))
        dict.__setitem__(self, attr, value)

    def __setattr__(self, attr, value):
        self[attr.replace('_', '-')] = value

    def __getattr__(self, attr):
        attr = attr.replace('_', '-')
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(
                "%r object has no attribute %r" % (
                self, attr))

    def __delattr__(self, attr):
        del self[attr.replace('_', '-')]

    def __contains__(self, value):
        return dict.__contains__(self, value.replace('_', '-'))

    def __repr__(self):
        return '<Properties %r>' % (dict.__repr__(self), )


class Component(object, log.Loggable):
    """I am a Component.
    A component has a name which identifies it and must be unique
    within a flow.
    A component has a list of feeders and a list of eaters and must
    belong to a worker. The feeder list or the eater list can be empty,
    but not both at the same time.
    @cvar eaterType: restrict the eaters which can be linked with this
      component to this type
    @cvar feederType: restrict the feeders which can be linked with this
      component to this type
    @cvar componentType: the type of the component, such as ogg-muxer,
      this is not mandatory in the class, can also be set in the instance.
    @cvar isAtmosphereComponent: if this component should live in
      the atmosphere instead of in a flow
    @ivar name: name of the component
    @ivar exists: if the component already exists, if this is set to true,
      a configuration saver or validator might chose to ignore this component
    """
    eaterType = None
    feederType = None
    componentType = None
    isAtmosphereComponent = False

    def __init__(self, worker=None):
        self.name = None
        self.worker = worker
        self.feeders = []
        self.eaters = []
        self.properties = Properties()
        self.plugs = []
        self.exists = False

    def __repr__(self):
        return '<%s.%s name=%r>' % (self.__class__.__module__,
                                    self.__class__.__name__, self.name)

    def __eq__(self, other):
        if not isinstance(other, Component):
            return False

        return (self.worker == other.worker and
                self.componentType == other.componentType)

    def __ne__(self, other):
        return not self.__eq__(other)

    # Backwards compatibility

    @property
    def component_type(self):
        import warnings
        warnings.warn('Use %s.componentType' % (self.__class__.__name, ),
                      DeprecationWarning, stacklevel=2)
        return self.componentType

    def validate(self):
        if not self.worker:
            raise ComponentValidationError(
                "component %s must have a worker set" % (self.name, ))

    def getWorker(self):
        return self.worker

    def getProperties(self):
        return Properties(self.properties)

    def getPlugs(self):
        return self.plugs

    def addPlug(self, plug):
        """
        Add a plug to the component
        @param plug: the plug
        @type plug: L{Plug}
        """
        self.plugs.append(plug)

    def delPlug(self, plug):
        plug in self.plugs and self.plugs.remove(plug)

    def link(self, component):
        """Link two components together
        @param component: component to link with
        @type component: Component
        """
        if not isinstance(component, Component):
            raise TypeError(
                "component must be a Component, not %r" % (component, ))
        self.feeders.append(component)
        component.eaters.append(self)

    def unlink(self, component):
        """Unlink two components from each other
        @param component: component to unlink from
        @type component: Component
        """
        if not isinstance(component, Component):
            raise TypeError(
                "component must be a Component, not %r" % (component, ))

        self.feeders.remove(component)
        component.eaters.remove(self)

    def getEaters(self):
        """Get the names of all the eaters for this component
        @returns: feeder names
        """

        # Figure out the feeder names to use.
        # Ask the feeder component which name it wants us to use
        for source in self.eaters:
            feederName = source.getFeederName(self)
            if feederName is None:
                feederName = ''
            else:
                feederName = ':' + feederName

            yield source.name + feederName

    def getFeederName(self, component):
        """Get the feeder name a component should use to link to
        @param component: the component who links to this
        @type component: L{Component} subclass
        @returns: feeder name
        @rtype: string
        """


class Plug(object):
    """I am a Plug.
    A plug has a name which identifies it and must be unique
    within a flow.
    @cvar plugType: the type of the plug, such as cortado,
      this is not mandatory in the class, can also be set in the instance.
    """

    def __init__(self):
        self.properties = Properties()

    def getProperties(self):
        return Properties(self.properties)


class Producer(Component):
    """I am a component which produces data.
    """

    def validate(self):
        super(Producer, self).validate()

        if self.eaters:
            raise ComponentValidationError(
                "producer component %s can not have any eaters" %
                (self.name, ))

        if not self.feeders:
            log.debug("component-validation",
                      "producer component %s doesn't have any feeder" %
                      (self.name, ))

    def getProperties(self):
        properties = super(Producer, self).getProperties()
        if 'framerate' in properties:
            # Convert framerate to fraction
            try:
                framerate = fractionFromValue(properties['framerate'])
            except ValueError:
                pass
            else:
                properties['framerate'] = "%d/%d" % framerate
        return properties


class Encoder(Component):
    """I am a component which encodes data
    """

    def validate(self):
        super(Encoder, self).validate()

        if not self.eaters:
            raise ComponentValidationError(
                "encoder component %s must have at least one eater" %
                (self.name, ))

        if not self.feeders:
            log.debug("component-validation",
                      "encoder component %s doesn't have any feeder" %
                      (self.name, ))


class Muxer(Component):
    """I am a component which muxes data from different components together.
    """

    def validate(self):
        super(Muxer, self).validate()

        if not self.eaters:
            raise ComponentValidationError(
                "muxer component %s must have at least one eater" %
                (self.name, ))

        if not self.feeders:
            log.debug("component-validation",
                      "muxer component %s doesn't have any feeder" %
                      (self.name, ))


class Consumer(Component):
    eaterType = Muxer
    requiresPorter = False
    prefix = "consumer"

    def __init__(self, worker=None):
        Component.__init__(self, worker)
        self._porter = None

    def validate(self):
        super(Consumer, self).validate()

        if not self.isAtmosphereComponent:
            if not self.eaters:
                raise ComponentValidationError(
                    "consumer component %s must have at least one eater" %
                    (self.name, ))
            if self.feeders:
                raise ComponentValidationError(
                    "consumer component %s cannot have feeders" %
                    (self.name, ))

    def setPorter(self, porter):
        self._porter = porter

    def getPorter(self):
        return self._porter


class AudioProducer(Producer):
    """I am a component which produces audio
    """


class VideoProducer(Producer):
    """I am a component which produces video
    """

    def getFramerate(self):
        """Get the framerate video producer
        @returns: the framerate
        @rtype: fraction: 2 sized tuple of two integers
        """
        return fractionFromValue(self.getProperties().framerate)

    def getWidth(self):
        """Get the width of the video producer
        @returns: the width
        @rtype: integer
        """
        return self.getProperties().width

    def getHeight(self):
        """Get the height of the video producer
        @returns: the height
        @rtype: integer
        """
        return self.getProperties().height


class VideoConverter(Component):
    """I am a component which converts video
    """


class AudioEncoder(Encoder):
    """I am a component which encodes audio
    """

    eaterType = AudioProducer


class VideoEncoder(Encoder):
    """I am a component which encodes video
    """

    eaterType = VideoProducer


class HTTPServer(Component):
    componentType = 'http-server'
    isAtmosphereComponent = True

    def __init__(self, worker, mountPoint):
        """
        @param mountPoint:
        @type  mountPoint:
        """
        super(HTTPServer, self).__init__(worker=worker)

        self.properties.mount_point = mountPoint


class HTTPPlug(Plug):

    def __init__(self, server, streamer, audioProducer, videoProducer):
        """
        @param server: server
        @type  server: L{HTTPServer} subclass
        @param streamer: streamer
        @type  streamer: L{HTTPStreamer}
        @param audioProducer: audio producer
        @type  audioProducer: L{flumotion.admin.assistant.models.AudioProducer}
          subclass or None
        @param videoProducer: video producer
        @type  videoProducer: L{flumotion.admin.assistant.models.VideoProducer}
          subclass or None
        """
        super(HTTPPlug, self).__init__()
        self.server = server
        self.streamer = streamer
        self.audioProducer = audioProducer
        self.videoProducer = videoProducer


class Porter(Component):
    """I am a model representing the configuration file for a
    porter component.
    """
    componentType = 'porter'
    isAtmosphereComponent = True

    def __init__(self, worker, port, username=None, password=None,
                 socketPath=None):
        super(Porter, self).__init__(worker=worker)

        self.properties.port = port
        if username is None:
            username = _generateRandomString(12)
        self.properties.username = username

        if password is None:
            password = _generateRandomString(12)
        self.properties.password = password

        if socketPath is None:
            socketPath = 'flu-%s.socket' % (_generateRandomString(6), )
        self.properties.socket_path = socketPath

    # Public API

    def getPort(self):
        return self.properties.port

    def getSocketPath(self):
        return self.properties.socket_path

    def getUsername(self):
        return self.properties.username

    def getPassword(self):
        return self.properties.password

    # Component

    def getProperties(self):
        properties = super(Porter, self).getProperties()
        properties.port = int(properties.port)
        return properties
