# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""widget holder displaying a component specific views"""

import gettext
import os

import gobject
import gtk

from flumotion.common import componentui, log, errors, messages
from flumotion.common.common import pathToModuleName
from flumotion.common.planet import AdminComponentState, moods
from flumotion.common.i18n import N_, gettexter
from gettext import gettext as _

T_ = gettexter()

# ensure unjellier registered
componentui # pyflakes

__version__ = "$Rev$"
_ = gettext.gettext
_DEBUG_ONLY_PAGES = ['Eaters', 'Feeders', 'Properties']
(COMPONENT_UNSET,
 COMPONENT_INACTIVE,
 COMPONENT_ACTIVE) = range(3)


class Placeholder(object):
    """A placeholder contains a Widget subclass of a specific
    component.
    """

    def getWidget(self):
        raise NotImplementedError(
            "%r must implement a getWidget() method")

    def setDebugEnabled(self, enabled):
        """Set if debug should be enabled.
        Not all pages are visible unless debugging is set to true
        @param enable: if debug should be enabled
        """

    def removed(self):
        """Called when the placeholder is inactivated, eg
        detached from the parent"""


class NotebookPlaceholder(Placeholder, log.Loggable):
    """This is a placeholder containing a notebook with tabs
    """
    logCategory = 'nodebook'

    def __init__(self, admingtk):
        """
        @param admingtk: the GTK Admin with its nodes
        @type  admingtk: L{flumotion.component.base.admin_gtk.BaseAdminGtk}
        """
        self._debugEnabled = False
        self._admingtk = admingtk
        self._notebook = None
        self._pageWidgets = {}

        self._notebook = gtk.Notebook()
        admingtk.setup()
        self.nodes = admingtk.getNodes()
        self._appendPages()
        self._notebook.show()

    # BaseComponentHolder

    def getWidget(self):
        return self._notebook

    def removed(self):
        if self._admingtk:
            # needed for compatibility with managers with old code
            if hasattr(self._admingtk, 'cleanup'):
                self._admingtk.cleanup()
            self._admingtk = None

    def setDebugEnabled(self, enabled):
        self._debugEnabled = enabled
        if self._admingtk:
            self._admingtk.setDebugEnabled(enabled)
        for name in _DEBUG_ONLY_PAGES:
            widget = self._pageWidgets.get(name)
            if widget is None:
                continue
            widget.set_property('visible', enabled)

    def _renderWidget(self, widget, table):
        # dumb dumb dumb dumb
        old_parent = widget.get_parent()
        if old_parent:
            old_parent.remove(widget)
        map(table.remove, table.get_children())
        table.add(widget)
        widget.show()

    def _addPage(self, name):
        node = self.nodes.get(name)
        assert node is not None, name

        table = gtk.Table(1, 1)
        table.add(gtk.Label(_('Loading UI for %s...') % name))
        label = self._getTitleLabel(node, name)
        label.show()
        self._notebook.append_page(table, label)

        d = node.render()
        d.addCallback(self._renderWidget, table)
        return table

    def _appendPages(self):
        for name in self.nodes.keys():
            table = self._addPage(name)
            self._pageWidgets[name] = table

            if name in _DEBUG_ONLY_PAGES:
                if self._debugEnabled:
                    continue
            table.show()

    def _getTitleLabel(self, node, name):
        title = node.title
        if not title:
            # FIXME: we have no way of showing an error message ?
            # This should be added so users can file bugs.
            self.warning("Component node %s does not have a "
                         "translatable title. Please file a bug." % name)

            # fall back for now
            title = name

        return gtk.Label(title)


class LabelPlaceholder(Placeholder):
    """This is a placeholder with a label, with or without a text"""

    def __init__(self, text=''):
        self._label = gtk.Label(text)

    def getWidget(self):
        return self._label


class PlanetPlaceholder(Placeholder):
    """This is a placeholder used to display a Planet"""

    def __init__(self):
        self._widget = gtk.Label('')

    def getWidget(self):
        return self._widget


class ComponentView(gtk.VBox, log.Loggable):
    logCategory = 'componentview'

    def __init__(self):
        gtk.VBox.__init__(self)
        self._admin = None
        self._currentComponentState = None
        self._currentPlaceholder = None
        self._debugEnabled = False
        self._state = COMPONENT_UNSET

        self._planetPlaceholder = PlanetPlaceholder()
        self._addPlaceholder(self._planetPlaceholder)

    # Public API

    def getDebugEnabled(self):
        """Find out if debug is enabled
        @returns: if debug is enabled
        @rtype: bool
        """
        return self._debugEnabled

    def setDebugEnabled(self, enabled):
        """Sets if debug should be enabled
        @param enabled: if debug should be enabled
        @type enabled: bool
        """
        self._debugEnabled = enabled
        if self._currentPlaceholder:
            self._currentPlaceholder.setDebugEnabled(enabled)

    def activateComponent(self, component):
        """Activates a component in the view
        @param component: component to show
        @type component: L{flumotion.common.component.AdminComponentState}
        """
        self._setState(COMPONENT_UNSET)
        if component:
            self._currentComponentState = component
            self._setState(COMPONENT_INACTIVE)

    def setSingleAdmin(self, admin):
        """
        Sets a single global admin for the component view

        @param admin: the admin
        @type  admin: L{flumotion.admin.admin.AdminModel}
        """
        self._admin = admin

    def getAdminForComponent(self, component):
        """
        Get the admin for a specific component

        @param component: component
        @type  component: L{flumotion.common.component.AdminComponentState}

        @returns: the admin
        @rtype:   L{flumotion.admin.admin.AdminModel}
        """
        # override me to do e.g. multi.getAdminForComponent
        return self._admin

    # Private

    def _addPlaceholder(self, placeholder):
        if not isinstance(placeholder, Placeholder):
            raise AssertionError(
                "placeholder must be a Placeholder subclass, not %r" % (
                placeholder, ))

        widget = placeholder.getWidget()
        widget.show()
        map(self.remove, self.get_children())
        self.pack_start(widget, True, True)

        placeholder.setDebugEnabled(self._debugEnabled)
        self._currentPlaceholder = placeholder

    def _removePlaceholder(self, placeholder):
        widget = placeholder.getWidget()
        self.remove(widget)

        placeholder.removed()

    def _getWidgetConstructor(self, componentState):
        if not isinstance(componentState, AdminComponentState):
            return LabelPlaceholder()

        def noBundle(failure):
            failure.trap(errors.NoBundleError)
            self.debug(
                'No specific GTK admin for this component, using default')
            return ("flumotion/component/base/admin_gtk.py", "BaseAdminGtk")

        def oldVersion(failure):
            # This is compatibility with platform-3
            # FIXME: It would be better to do this using strict
            #        version checking of the manager

            # File ".../flumotion/manager/admin.py", line 278, in
            #   perspective_getEntryByType
            # exceptions.AttributeError: 'str' object has no attribute 'get'
            failure.trap(AttributeError)

            return admin.callRemote(
                'getEntryByType', componentState, 'admin/gtk')

        def gotEntryPoint((filename, procname)):
            # The manager always returns / as a path separator, replace them
            # with the separator since the rest of our infrastructure depends
            # on that.
            filename = filename.replace('/', os.path.sep)
            # getEntry for admin/gtk returns a factory function for creating
            # flumotion.component.base.admin_gtk.BaseAdminGtk
            # subclass instances
            modname = pathToModuleName(filename)

            # we call hostile code, so we should handle exceptions:
            d = admin.getBundledFunction(modname, procname)
            d.addErrback(admin.bundleErrback, filename)

            def handleSyntaxError(failure):
                failure.trap(errors.EntrySyntaxError)
                msg = failure.value.args[0]

                m = messages.Error(T_(
                    N_("This component has a UI bug.")), debug=msg)
                componentState.observe_append('messages', m)

                raise errors.HandledException(failure.value)

            d.addErrback(handleSyntaxError)

            return d

        def gotFactory(factory):
            # instantiate from factory and wrap in a NotebookPlaceHolder
            widget = factory(componentState, admin)
            return NotebookPlaceholder(widget)

        def sleepingComponent(failure):
            failure.trap(errors.SleepingComponentError)
            return LabelPlaceholder(_("Component '%s' is still sleeping.") %
                                    componentState.get('name'))

        def handledExceptionErrback(failure):
            # already handle, so let call chain short-circuit here and
            # just return
            failure.trap(errors.HandledException)
            return LabelPlaceholder(_("Component '%s' has a UI bug.") %
                                    componentState.get('name'))

        admin = self.getAdminForComponent(componentState)
        componentType = componentState.get('type')
        d = admin.callRemote('getEntryByType', componentType, 'admin/gtk')
        d.addErrback(oldVersion)
        d.addErrback(noBundle)
        d.addCallback(gotEntryPoint)
        d.addCallback(gotFactory)
        d.addErrback(sleepingComponent)
        d.addErrback(handledExceptionErrback)
        return d

    def _componentUnsetToInactive(self):

        def invalidate(_):
            self._setState(COMPONENT_UNSET)

        def set_(state, key, value):
            if key != 'mood':
                return
            if value not in [moods.lost.value,
                             moods.sleeping.value,
                             moods.sad.value]:
                self._setState(COMPONENT_ACTIVE)
            else:
                self._setState(COMPONENT_INACTIVE)

        current = self._currentComponentState
        assert current is not None
        current.addListener(self, invalidate=invalidate, set_=set_)
        if current.hasKey('mood'):
            set_(current, 'mood', current.get('mood'))

    def _componentInactiveToActive(self):

        def gotWidgetConstructor(placeholder, oldComponentState):
            if oldComponentState != self._currentComponentState:
                # in the time that _get_widget_constructor was running,
                # perhaps the user selected another component; only update
                # the ui if that did not happen
                self.debug('ignoring component %r, state %d, state %r/%r' % (
                    placeholder, self._state,
                    oldComponentState, self._currentComponentState))
                return
            self._removePlaceholder(self._planetPlaceholder)
            self._addPlaceholder(placeholder)

        d = self._getWidgetConstructor(self._currentComponentState)
        d.addCallback(gotWidgetConstructor, self._currentComponentState)

    def _componentActiveToInactive(self):
        self._removePlaceholder(self._currentPlaceholder)
        self._addPlaceholder(self._planetPlaceholder)

    def _componentInactiveToUnset(self):
        if self._currentComponentState:
            self._currentComponentState.removeListener(self)
        self._currentComponentState = None

    def _setState(self, state):
        uptable = [self._componentUnsetToInactive,
                   self._componentInactiveToActive]
        downtable = [self._componentInactiveToUnset,
                     self._componentActiveToInactive]
        if self._state < state:
            while self._state < state:
                self.log('component %r state change: %d++',
                         self._currentComponentState, self._state)
                self._state += 1
                uptable[self._state - 1]()
        else:
            while self._state > state:
                self.log('component %r state change: %d--',
                         self._currentComponentState, self._state)
                self._state -= 1
                downtable[self._state]()

gobject.type_register(ComponentView)
