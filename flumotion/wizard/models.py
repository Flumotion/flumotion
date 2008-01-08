# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2007 Fluendo, S.L. (www.fluendo.com).
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

__version__ = "$Rev$"

"""model objects used by the wizard steps"""


class ComponentError(Exception):
    pass


class ComponentValidationError(ComponentError):
    pass


class Properties(dict):
    """
    I am a special dictionary which you also can treat as an instance.
    Setting and getting an attribute works.
    This is suitable for using in a kiwi proxy.
    >>> p = Properties()
    >>> p.attr = 'value'
    >>> p
    {'attr': 'value'}
    """
    def __setattr__(self, attr, value):
        self[attr] = value

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(attr)


class Flow(object):
    """I am a container which contains a number of components
    """

    def __init__(self, name=None):
        """Creates a new flow
        @param name: optional, name of the flow
        @type name string
        """
        self.name = name
        self._components = []
        self._names = {}

    def __iter__(self):
        return iter(self._components)

    def __contains__(self, component):
        return component in self._components

    def addComponent(self, component):
        """Adds a component to the flow.
        A component can only belong to one flow at a time,
        you cannot add the same component several times to the same flow
        @param component: component to add
        @type component: L{Component}
        """
        if not isinstance(component, Component):
            raise TypeError(
                "component must be a Component type, not %s" % (
                    type(component).__name__,))
        if component in self._components:
            raise ComponentError(
                "the component %r is already in the flow" % (
                    component,))

        component.name = self._getNameForComponent(component)
        self._names[component.name] = component
        self._components.append(component)

    def removeComponent(self, component):
        """Removes a component from the flow.
        A component must belong to the flow to be able to remove it
        @param component: component to remove
        @type component: L{Component}
        """
        if not isinstance(component, Component):
            raise TypeError(
                "component must be a Component type, not %s" % (
                    type(component).__name__,))
        if not component in self._components:
            raise ComponentError(
                "the component %r is not in the flow" % (
                    component,))

        self._components.remove(component)
        del self._names[component.name]
        component.name = None

    def _getNameForComponent(self, component):
        # component, component-2, component-3, ...
        name = component.name_template
        i = 2
        while name in self._names:
            name = "%s-%d" % (component.name_template, i)
            i += 1
        return name


class Component(object):
    """I am a Component.
    A component has a name which identifies it and must be unique
    within a flow.
    A component has a list of feeders and a list of eaters and must
    belong to a worker. The feeder list or the eater list can be empty,
    but not both at the same time.
    @cvar eater_type: restrict the eaters which can be linked with this
      component to this type
    @cvar feeder_type: restrict the feeders which can be linked with this
      component to this type
    @cvar name_template: template used to define the name of this component
    """
    eater_type = None
    feeder_type = None
    name_template = "component"

    def __init__(self):
        self.component_type = None
        self.worker = None
        self.feeders = []
        self.eaters = []
        self.properties = Properties()

    def validate(self):
        if not self.worker:
            raise ComponentValidationError(
                "component %s must have a worker set" % (self.name,))

    def getWorker(self):
        return self.worker

    def getProperties(self):
        return self.properties


class Producer(Component):
    """I am a component which produces data.
    """
    name_template = "producer"

    def validate(self):
        super(Component, self).validate()

        if self.eaters:
            raise ComponentValidationError(
                "producer component %s can not have any easters" %
                (self.name,))

        if not self.feeders:
            raise ComponentValidationError(
                "producer component %s must have at least one feeder" %
                (self.name,))


class Encoder(Component):
    """I am a component which encodes data
    """
    name_template = "encoder"

    def validate(self):
        super(Component, self).validate()

        if not self.eaters:
            raise ComponentValidationError(
                "encoder component %s must have at least one eater" %
                (self.name,))

        if not self.feeders:
            raise ComponentValidationError(
                "encoder component %s must have at least one feeder" %
                (self.name,))


class Muxer(Component):
    """I am a component which muxes data from different components together.
    """
    name_template = "muxer"

    def validate(self):
        super(Component, self).validate()

        if not self.eaters:
            raise ComponentValidationError(
                "muxer component %s must have at least one eater" %
                (self.name,))

        if not self.feeders:
            raise ComponentValidationError(
                "muxer component %s must have at least one feeder" %
                (self.name,))


class Consumer(Component):
    eater_type = Muxer
    name_template = "consumer"

    def validate(self):
        super(Component, self).validate()

        if not self.eaters:
            raise ComponentValidationError(
                "consumer component %s must have at least one eater" %
                (self.name,))

        if self.feeders:
            raise ComponentValidationError(
                "consumer component %s must have at least one feeder" %
                (self.name,))


class AudioProducer(Component):
    """I am a component which produces audio
    """
    name_template = "audio-producer"


class VideoProducer(Producer):
    """I am a component which produces video
    """
    name_template = "video-producer"


class AudioEncoder(Encoder):
    """I am a component which encodes audio
    """

    eater_type = AudioProducer
    name_template = "audio-encoder"


class VideoEncoder(Encoder):
    """I am a component which encodes video
    """

    eater_type = VideoProducer
    name_template = "video-encoder"
