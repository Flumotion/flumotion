# -*- Mode: Python; test-case-name: flumotion.test.test_wizard -*-
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

import operator
from cStringIO import StringIO
from xml.sax.saxutils import quoteattr

from flumotion.common.xmlwriter import cmpComponentType, XMLWriter
from flumotion.configure import configure

__version__ = "$Rev: 6246 $"


class ConfigurationWriter(XMLWriter):
    """I am responsible for writing the state of a flow created by the
    configuration assistant into XML.
    I will try my best write pretty XML which can be editable by humans at a
    later point.
    """

    def __init__(self, flowName, flowComponents, atmosphereComponents):
        """
        @param flowName: name of the flow
        @param flowComponents: components to be included in the flow
        @param atmosphereComponents: components to be included
            in the atmosphere
        """
        super(ConfigurationWriter, self).__init__()
        self._flowName = flowName
        self._flowComponents = flowComponents
        self._atmosphereComponents = atmosphereComponents
        self._writePlanet()

    def _writePlanet(self):
        self.pushTag('planet')
        self._writeAtmosphere(self._atmosphereComponents)
        self._writeFlow(self._flowName, self._flowComponents)
        self.popTag()

    def _writeAtmosphere(self, components):
        if not components:
            return
        self.pushTag('atmosphere')
        self._writeComponents(components)
        self.popTag()

    def _writeFlow(self, flowName, components):
        if not components:
            return
        self.pushTag('flow', [('name', flowName)])
        self._writeComponents(components)
        self.popTag()

    def _writeComponents(self, components):
        components = sorted(components,
                            cmp=cmpComponentType,
                            key=operator.attrgetter('componentType'))
        for component in components:
            self._writeComponent(component)

    def _writeComponent(self, component):
        # Do not write components which already exists in the flow,
        # This is used to create configuration snippets sent to the
        # asssistant which links to existing components
        if component.exists:
            return

        # FIXME: when the assistant can be split among projects, "project"
        # and "version" should be taken from the relevant project
        attrs = [('name', component.name),
                 ('type', component.componentType),
                 ('project', configure.PACKAGE),
                 ('worker', component.worker),
                 ('version', configure.version)]
        self.pushTag('component', attrs)
        self._writeEaters(component.getEaters())
        self._writeProperties(component.getProperties())
        self._writeComponentPlugs(component.plugs)
        self.popTag()

    def _writeEaters(self, eaters):
        eaters = list(eaters)
        if not eaters:
            return
        self.pushTag('eater', [('name', "default")])
        for sourceName in eaters:
            self.writeTag('feed', data=sourceName)
        self.popTag()

    def _writeProperties(self, properties):
        if not properties:
            return
        self.writeLine()
        propertyNames = properties.keys()
        propertyNames.sort()
        for name in propertyNames:
            value = properties[name]
            # Fractions, perhaps we should do type introspection here?
            if isinstance(value, tuple):
                assert len(value) == 2
                value = '%d/%d' % value
            self.writeTag('property', [('name', name)], value)

    def _writeComponentPlugs(self, plugs):
        if not plugs:
            return
        self.writeLine()
        self.pushTag('plugs')
        for plug in plugs:
            self._writeComponentPlug(plug)
        self.popTag()

    def _writeComponentPlug(self, plug):
        self.pushTag('plug', [('type', plug.plugType)])
        self._writeProperties(plug.getProperties())
        self.popTag()
