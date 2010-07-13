# -*- Mode: Python; test-case-name: flumotion.test.test_manager_admin -*-
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
manager-side objects to handle administrative clients
"""

import re
import os
import errno
from StringIO import StringIO

from twisted.internet import reactor
from twisted.python import failure
from twisted.spread import pb
from zope.interface import implements

from flumotion.manager import base
from flumotion.common import errors, interfaces, log, planet, registry, debug
from flumotion.common import common
from flumotion.common.python import makedirs
from flumotion.monitor.nagios import util

# make Result and Message proxyable
from flumotion.common import messages

# make ComponentState proxyable
from flumotion.twisted import flavors
from flumotion.common import componentui

__version__ = "$Rev$"


# FIXME: rename to Avatar since we are in the admin. namespace ?


class AdminAvatar(base.ManagerAvatar):
    """
    I am an avatar created for an administrative client interface.
    A reference to me is given (for example, to gui.AdminInterface)
    when logging in and requesting an "admin" avatar.
    I live in the manager.
    """
    logCategory = 'admin-avatar'

    # override pb.Avatar implementation so we can run admin actions

    def perspectiveMessageReceived(self, broker, message, args, kwargs):
        benignMethods = ('ping', )

        args = broker.unserialize(args)
        kwargs = broker.unserialize(kwargs)

        if message not in benignMethods:
            self.vishnu.adminAction(self.remoteIdentity, message, args, kwargs)

        return base.ManagerAvatar.perspectiveMessageReceivedUnserialised(
            self, broker, message, args, kwargs)

    ### pb.Avatar IPerspective methods

    def perspective_getPlanetState(self):
        """
        Get the planet state.

        @rtype: L{flumotion.common.planet.ManagerPlanetState}
        """
        self.debug("returning planet state %r" % self.vishnu.state)
        return self.vishnu.state

    def perspective_getWorkerHeavenState(self):
        """
        Get the worker heaven state.

        @rtype: L{flumotion.common.worker.ManagerWorkerHeavenState}
        """
        self.debug("returning worker heaven state %r" % self.vishnu.state)
        return self.vishnu.workerHeaven.state

    def perspective_componentStart(self, componentState):
        """
        Start the given component.  The component should be sleeping before
        this.

        @type componentState: L{planet.ManagerComponentState}
        """
        self.debug('perspective_componentStart(%r)' % componentState)
        return self.vishnu.componentCreate(componentState)

    def perspective_componentStop(self, componentState):
        """
        Stop the given component.
        If the component was sad, we clear its sad state as well,
        since the stop was explicitly requested by the admin.

        @type componentState: L{planet.ManagerComponentState}
        """
        self.debug('perspective_componentStop(%r)' % componentState)
        return self.vishnu.componentStop(componentState)

    def perspective_componentRestart(self, componentState):
        """
        Restart the given component.

        @type componentState: L{planet.ManagerComponentState}
        """
        self.debug('perspective_componentRestart(%r)' % componentState)
        d = self.perspective_componentStop(componentState)
        d.addCallback(lambda *x: self.perspective_componentStart(
            componentState))
        return d

    # Generic interface to call into a component

    def perspective_componentCallRemote(self, componentState, methodName,
                                        *args, **kwargs):
        """
        Call a method on the given component on behalf of an admin client.

        @param componentState: state of the component to call the method on
        @type  componentState: L{planet.ManagerComponentState}
        @param methodName:     name of the method to call.  Gets proxied to
                               L{flumotion.component.component.""" \
                               """BaseComponentMedium}'s remote_(methodName)
        @type  methodName:     str

        @rtype: L{twisted.internet.defer.Deferred}
        """
        assert isinstance(componentState, planet.ManagerComponentState), \
            "%r is not a componentState" % componentState

        if methodName == "start":
            self.warning('forwarding "start" to perspective_componentStart')
            return self.perspective_componentStart(componentState)

        m = self.vishnu.getComponentMapper(componentState)
        if not m:
            self.warning('Component not mapped. Maybe deleted.')
            raise errors.UnknownComponentError(componentState)

        avatar = m.avatar

        if not avatar:
            self.warning('No avatar for %s, cannot call remote' %
                componentState.get('name'))
            raise errors.SleepingComponentError(componentState)

        # XXX: Maybe we need to have a prefix, so we can limit what an
        # admin interface can call on a component
        try:
            return avatar.mindCallRemote(methodName, *args, **kwargs)
        except Exception, e:
            msg = "exception on remote call %s: %s" % (methodName,
                log.getExceptionMessage(e))
            self.warning(msg)
            raise errors.RemoteMethodError(methodName,
                log.getExceptionMessage(e))

    def perspective_componentsList(self):
        """
        List components in the planet. Returns a list of avatar ids.
        """
        componentStates = self.vishnu.state.getComponents()
        avatar_ids = [common.componentId(c.get('parent').get('name'),
                                         c.get('name'))
                      for c in componentStates]
        return avatar_ids

    def perspective_componentInvoke(self, avatarId, methodName,
                                    *args, **kwargs):
        """
        Call a remote method on the component.

        @param avatarId: the component avatar id
        @type  avatarId: str
        @param methodName: name of the method to call
        @type  methodName: str
        """
        component = util.findComponent(self.vishnu.state, avatarId)
        if not component:
            self.warning('No component with avatar id %s' % avatarId)
            raise errors.UnknownComponentError(avatarId)
        return self.perspective_componentCallRemote(component, methodName,
                                                    *args, **kwargs)

    def perspective_upstreamList(self, avatarId):
        """
        List a component and its upstream components along with
        types and worker hosts.

        @param avatarId: the component avatar id
        @type  avatarId: str
        """

        def get_eaters_ids(eaters_dic):
            avatars = []
            for flow in eaters_dic.keys():
                comps = eaters_dic[flow]
                for c in comps:
                    (name, what) = c[0].split(':')
                    avatars.append('/%s/%s' % (flow, name))
            return avatars

        def create_response(components, workers):
            comps = []
            for c in components:
                workerName = c.get('workerName')
                host = "unknown"
                for w in workers:
                    if workerName == w.get('name'):
                        host = w.get('host')
                        break
                comps.append((c.get('name'), c.get('type'), host))
            return comps

        component = util.findComponent(self.vishnu.state, avatarId)
        if not component:
            self.warning('No component with avatar id %s' % avatarId)
            raise errors.UnknownComponentError(avatarId)

        eaters = component.get('config').get('eater', {})
        eaters_id = get_eaters_ids(eaters)
        comps = [component]
        while len(eaters_id) > 0:
            eaters = {}
            for i in eaters_id:
                try:
                    compState = util.findComponent(self.vishnu.state, i)
                    comps.append(compState)
                    eaters.update(compState.get('config').get('eater', {}))
                except Exception, e:
                    self.debug(log.getExceptionMessage(e))
                    emsg = "Error retrieving component '%s'" % i
                    raise errors.UnknownComponentError(emsg)
            eaters_id = get_eaters_ids(eaters)

        workers = self.vishnu.workerHeaven.state.get('workers')
        return create_response(comps, workers)

    def perspective_workerCallRemote(self, workerName, methodName,
                                     *args, **kwargs):
        """
        Call a remote method on the worker.
        This is used so that admin clients can call methods from the interface
        to the worker.

        @param workerName: the worker to call
        @type  workerName: str
        @param methodName: Name of the method to call.  Gets proxied to
                           L{flumotion.worker.medium.WorkerMedium} 's
                           remote_(methodName)
        @type  methodName: str
        """

        self.debug('AdminAvatar.workerCallRemote(%r, %r)' % (
            workerName, methodName))
        workerAvatar = self.vishnu.workerHeaven.getAvatar(workerName)

        # XXX: Maybe we need to a prefix, so we can limit what an admin
        # interface can call on a worker
        try:
            return workerAvatar.mindCallRemote(methodName, *args, **kwargs)
        except Exception, e:
            self.warning("exception on remote call: %s" %
                log.getExceptionMessage(e))
            return failure.Failure(errors.RemoteMethodError(methodName,
                log.getExceptionMessage(e)))

    def perspective_getEntryByType(self, componentType, entryType):
        """
        Get the entry point for a piece of bundled code in a component by type.
        @param componentType: the component
        @type componentType: a string
        @param entryType: location of the entry point
        @type entryType: a string
        Returns: a (filename, methodName) tuple, or raises::
          - NoBundleError if the entry location does not exist
        """
        assert componentType is not None

        self.debug('getting entry of type %s for component type %s',
                   entryType, componentType)

        try:
            componentRegistryEntry = registry.getRegistry().getComponent(
                componentType)
            # FIXME: add logic here for default entry points and functions
            entry = componentRegistryEntry.getEntryByType(entryType)
        except KeyError:
            self.warning("Could not find bundle for %s(%s)" % (
                componentType, entryType))
            raise errors.NoBundleError("entry type %s in component type %s" %
                (entryType, componentType))

        filename = os.path.join(componentRegistryEntry.base, entry.location)
        self.debug('entry point is in file path %s and function %s' % (
            filename, entry.function))
        return (filename, entry.function)

    def perspective_getPlugEntry(self, plugType, entryType):
        """
        Get the entry point for a piece of bundled code in a plug by type.
        @param plugType: the plug
        @type plugType: a string
        @param entryType: location of the entry point
        @type entryType: a string
        Returns: a (filename, methodName) tuple, or raises::
          - NoBundleError if the entry location does not exist
        """
        assert plugType is not None

        self.debug('getting entry of type %s for plug type %s',
                   entryType, plugType)

        try:
            plugRegistryEntry = registry.getRegistry().getPlug(plugType)
            entry = plugRegistryEntry.getEntryByType(entryType)
        except KeyError:
            self.warning("Could not find bundle for %s(%s)" % (
                plugType, entryType))
            raise errors.NoBundleError("entry type %s in plug type %s" %
                                       (entryType, plugType))

        self.debug('entry point is in file path %s and function %s' % (
           entry.location, entry.function))
        return (entry.location, entry.function)

    def perspective_getConfiguration(self):
        """
        Get the configuration of the manager as an XML string.

        @rtype: str
        """
        return self.vishnu.getConfiguration()

    def perspective_getScenarioByType(self, scenarioType, entryType):
        """
        Remote method that gets the scenario of a given type.

        @param scenarioType: the component
        @type scenarioType: a string
        Returns: a (filename, methodName) tuple, or raises::
          - NoBundleError if the entry location does not exist
        """
        assert scenarioType is not None

        self.debug('getting entry of type %s for scenario type %s',
                   entryType, scenarioType)

        try:
            scenarioRegistryEntry = registry.getRegistry().getScenarioByType(
                scenarioType)
            # FIXME: add logic here for default entry points and functions
            entry = scenarioRegistryEntry.getEntryByType(entryType)
        except KeyError:
            self.warning("Could not find bundle for %s(%s)" % (
                scenarioType, entryType))
            raise errors.NoBundleError("entry type %s in component type %s" %
                (entryType, scenarioType))

        filename = os.path.join(scenarioRegistryEntry.getBase(),
                                entry.getLocation())
        self.debug('entry point is in file path %s and function %s' % (
            filename, entry.function))

        return (filename, entry.getFunction())

    def perspective_getScenarios(self):
        """
        Get all the scenarios defined on the registry.

        @rtype     : List of L{IScenarioAssistantPlugin}
        """
        r = registry.getRegistry()
        return r.getScenarios()

    def _saveFlowFile(self, filename):
        """Opens a file that the flow should be written to.

        Note that the returned file object might be an existing file,
        opened in append mode; if the loadConfiguration operation
        succeeds, the file should first be truncated before writing.
        """
        self.vishnu.adminAction(self.remoteIdentity,
                                '_saveFlowFile', (), {})

        def ensure_sane(name, extra=''):
            if not re.match('^[a-zA-Z0-9_' + extra + '-]+$', name):
                raise errors.ConfigError, \
                      'Invalid planet or saveAs name: %s' % name

        ensure_sane(self.vishnu.configDir, '/')
        ensure_sane(filename)
        directory = os.path.join(self.vishnu.configDir, "flows")
        self.debug('told to save flow as %s/%s.xml', directory, filename)
        try:
            makedirs(directory, 0770)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise e
        prev = os.umask(0007)
        output = open(os.path.join(directory, filename + '.xml'), 'a')
        os.umask(prev)
        return output

    def perspective_loadConfiguration(self, xml, saveAs=None):
        """
        Load the given XML configuration into the manager. If the
        optional saveAs parameter is passed, the XML snippet will be
        saved to disk in the manager's flows directory.

        @param xml: the XML configuration snippet.
        @type  xml: str
        @param saveAs: The name of a file to save the XML as.
        @type  saveAs: str
        """

        if saveAs:
            output = self._saveFlowFile(saveAs)

        # Update the registry if needed, so that new/changed component types
        # can be parsed.
        registry.getRegistry().verify()

        f = StringIO(xml)
        res = self.vishnu.loadComponentConfigurationXML(f, self.remoteIdentity)
        f.close()

        if saveAs:

            def success(res):
                self.debug('loadConfiguration succeeded, writing flow to %r',
                           output)
                output.truncate(0)
                output.write(xml)
                output.close()
                return res

            def failure(res):
                self.debug('loadConfiguration failed, leaving %r as it was',
                           output)
                output.close()
                return res
            res.addCallbacks(success, failure)

        return res

    def perspective_loadComponent(self, componentType, componentId,
                                  componentLabel, properties, workerName,
                                  plugs=None, eaters=None,
                                  isClockMaster=None, virtualFeeds=None):
        """
        Load a component into the manager configuration.
        Returns a deferred that will be called with the component state.

        @param componentType:  The registered type of the component to be added
        @type  componentType:  str
        @param componentId:    The identifier of the component to add,
                               should be created by the function
                               L{flumotion.common.common.componentId}
        @type  componentId:    str
        @param componentLabel: The human-readable label of the component.
                               if None, no label will be set.
        @type  componentLabel: str or None
        @param properties:     List of property name-value pairs.
                               See L{flumotion.common.config.buildPropertyDict}
        @type  properties:     list of (str, object)
        @param workerName:     the name of the worker where the added
                               component should run.
        @type  workerName:     str
        @param plugs:          List of plugs, as type-propertyList pairs.
                               See {flumotion.manager.config.buildPlugsSet}.
        @type  plugs:          [(str, [(str, object)])]
        @param eaters:         List of (eater name, feed ID) pairs.
                               See L{flumotion.manager.config.buildEatersDict}
        @type  eaters:         [(str, str)]
        @param isClockMaster:  True if the component to be added must be
                               a clock master. Passing False here means
                               that the manager will choose what
                               component, if any, will be clock master
                               for this flow.
        @type  isClockMaster:  bool
        @param virtualFeeds:   List of (virtual feed, feeder name) pairs.
            See L{flumotion.manager.config.buildVirtualFeeds}
        @type  virtualFeeds:   [(str, str)]
        """
        return self.vishnu.loadComponent(self.remoteIdentity, componentType,
                                         componentId, componentLabel,
                                         properties, workerName,
                                         plugs or [], eaters or [],
                                         isClockMaster, virtualFeeds or [])

    def perspective_deleteFlow(self, flowName):
        return self.vishnu.deleteFlow(flowName)

    def perspective_deleteComponent(self, componentState):
        """Delete a component from the manager.

        A component can only be deleted when it is sleeping or sad. It
        is the caller's job to ensure this is the case; calling this
        function on a running component will raise a ComponentBusyError.

        @returns: a deferred that will fire when all listeners have been
        notified of the component removal
        """
        return self.vishnu.deleteComponent(componentState)

    def perspective_getVersions(self):
        return debug.getVersions()

    def perspective_cleanComponents(self):
        return self.vishnu.emptyPlanet()

    def perspective_getWizardEntries(self, types=None, provides=None,
                                     accepts=None):
        """
        Fetches the wizard entries which matches the parameters sent in

        @param types: list of component types to fetch, is usually
          something like ['video-producer'] or ['audio-encoder']
        @type  types: list of strings
        @param provides: formats provided, eg ['jpeg', 'speex']
        @type  provides: list of strings
        @param accepts: formats accepted, eg ['theora']
        @type  accepts: list of strings
        @returns: L{componentui.WizardEntryState}
        """

        def extract(wizards):
            for wizard in wizards:
                if types is not None:
                    if wizard.type not in types:
                        continue
                if provides is not None:
                    for format in wizard.provides:
                        if format.media_type in provides:
                            break
                    else:
                        continue
                if accepts is not None:
                    for format in wizard.accepts:
                        if format.media_type in accepts:
                            break
                    else:
                        continue
                yield wizard

        retval = []
        r = registry.getRegistry()
        for component in r.getComponents():
            retval += extract(component.wizards)
        for plug in r.getPlugs():
            retval += extract(plug.wizards)
        del r

        return retval

    def perspective_getComponentEntry(self, componentType):
        """Fetches a ComponentRegistryEntry given a componentType
        @param componentType: component type
        @type componentType: string
        @returns: the component
        @rtype: L{ComponentRegistryEntry}
        """
        try:
            componentRegistryEntry = registry.getRegistry().getComponent(
                componentType)
        except KeyError:
            return None
        return componentRegistryEntry

    def perspective_invokeOnComponents(self, componentType, methodName,
        *args, **kwargs):
        return self.vishnu.invokeOnComponents(componentType, methodName,
            *args, **kwargs)


class AdminHeaven(base.ManagerHeaven):
    """
    I interface between the Manager and administrative clients.
    For each client I create an L{AdminAvatar} to handle requests.
    I live in the manager.
    """

    logCategory = "admin-heaven"
    implements(interfaces.IHeaven)
    avatarClass = AdminAvatar
