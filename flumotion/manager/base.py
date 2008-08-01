# -*- Mode: Python; test-case-name: flumotion.test.test_manager_common -*-
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
common classes and code to support manager-side objects
"""

from twisted.internet import reactor, defer
from twisted.spread import pb, flavors
from twisted.python import failure, reflect

from flumotion.common import errors, interfaces, log, common
from flumotion.common.planet import moods
from flumotion.twisted import pb as fpb

__version__ = "$Rev$"


class ManagerAvatar(fpb.PingableAvatar, log.Loggable):
    """
    I am a base class for manager-side avatars to subclass from.

    @ivar avatarId: the id for this avatar, unique inside the heaven
    @type avatarId: str
    @ivar heaven:   the heaven this avatar is part of
    @type heaven:   L{flumotion.manager.base.ManagerHeaven}
    @ivar mind:     a remote reference to the client-side Medium
    @type mind:     L{twisted.spread.pb.RemoteReference}
    @ivar vishnu:   the vishnu that manages this avatar's heaven
    @type vishnu:   L{flumotion.manager.manager.Vishnu}
    """
    remoteLogName = 'medium'
    logCategory = 'manager-avatar'

    def __init__(self, heaven, avatarId, remoteIdentity, mind):
        """
        @param heaven:         the heaven this avatar is part of
        @type  heaven:         L{flumotion.manager.base.ManagerHeaven}
        @param avatarId:       id of the avatar to create
        @type  avatarId:       str
        @param remoteIdentity: manager-assigned identity object for this
                               avatar
        @type  remoteIdentity: L{flumotion.common.identity.RemoteIdentity}
        @param mind:           a remote reference to the client-side Medium
        @type  mind:           L{twisted.spread.pb.RemoteReference}
        """
        fpb.PingableAvatar.__init__(self, avatarId)
        self.heaven = heaven
        self.logName = avatarId
        self.setMind(mind)
        self.vishnu = heaven.vishnu
        self.remoteIdentity = remoteIdentity

        self.debug("created new Avatar with id %s", avatarId)

    def perspective_writeFluDebugMarker(self, level, marker):
        """
        Sets a marker that will be prefixed to the log strings. Setting this
        marker to multiple elements at a time helps debugging.
        @param marker: A string to prefix all the log strings.
        @param level: The log level. It can be log.ERROR, log.DEBUG,
                      log.WARN, log.INFO or log.LOG
        """

        self.writeMarker(marker, level)
        workers = self.vishnu.workerHeaven.state.get('names')
        componentStates = self.vishnu.getComponentStates()
        for worker in workers:
            self.perspective_workerCallRemote(worker, 'writeFluDebugMarker',
                                              level, marker)
        for componentState in componentStates:
            m = self.vishnu.getComponentMapper(componentState)
            if m.avatar:
                self.perspective_componentCallRemote(componentState,
                                                     'writeFluDebugMarker',
                                                 level, marker)

    def makeAvatarInitArgs(klass, heaven, avatarId, remoteIdentity, mind):
        return defer.succeed((heaven, avatarId, remoteIdentity, mind))
    makeAvatarInitArgs = classmethod(makeAvatarInitArgs)

    def makeAvatar(klass, heaven, avatarId, remoteIdentity, mind):
        log.debug('manager-avatar', 'making avatar with avatarId %s',
                  avatarId)

        def have_args(args):
            log.debug('manager-avatar', 'instantiating with args=%r', args)
            return klass(*args)
        d = klass.makeAvatarInitArgs(heaven, avatarId, remoteIdentity, mind)
        d.addCallback(have_args)
        return d
    makeAvatar = classmethod(makeAvatar)

    def onShutdown(self):
        self.stopPingChecking()

    def mindCallRemote(self, name, *args, **kwargs):
        """
        Call the given remote method, and log calling and returning nicely.

        @param name: name of the remote method
        @type  name: str
        """
        level = log.DEBUG
        if name == 'ping':
            level = log.LOG

        return self.mindCallRemoteLogging(level, -1, name, *args, **kwargs)

    def getClientAddress(self):
        """
        Get the IPv4 address of the machine the PB client is connecting from,
        as seen from the avatar.

        @returns:  the IPv4 address the client is coming from, or None.
        @rtype:   str or None
        """
        if self.mind:
            peer = self.mind.broker.transport.getPeer()
            return peer.host

        return None

    def perspective_getBundleSums(self, bundleName=None, fileName=None,
                                  moduleName=None):
        """
        Get a list of (bundleName, md5sum) of all dependency bundles,
        starting with this bundle, in the correct order.
        Any of bundleName, fileName, moduleName may be given.

        @type  bundleName: str or list of str
        @param bundleName: the name of the bundle for fetching
        @type  fileName:   str or list of str
        @param fileName:   the name of the file requested for fetching
        @type  moduleName: str or list of str
        @param moduleName: the name of the module requested for import

        @rtype: list of (str, str) tuples of (bundleName, md5sum)
        """
        bundleNames = []
        fileNames = []
        moduleNames = []
        if bundleName:
            if isinstance(bundleName, str):
                bundleNames.append(bundleName)
            else:
                bundleNames.extend(bundleName)
            self.debug('asked to get bundle sums for bundles %r' % bundleName)
        if fileName:
            if isinstance(fileName, str):
                fileNames.append(fileName)
            else:
                fileNames.extend(fileName)
            self.debug('asked to get bundle sums for files %r' % fileNames)
        if moduleName:
            if isinstance(moduleName, str):
                moduleNames.append(moduleName)
            else:
                moduleNames.extend(moduleName)
            self.debug('asked to get bundle sums for modules %r' % moduleNames)

        basket = self.vishnu.getBundlerBasket()

        # will raise an error if bundleName not known
        for fileName in fileNames:
            bundleName = basket.getBundlerNameByFile(fileName)
            if not bundleName:
                msg = 'containing ' + fileName
                self.warning('No bundle %s' % msg)
                raise errors.NoBundleError(msg)
            else:
                bundleNames.append(bundleName)

        for moduleName in moduleNames:
            bundleName = basket.getBundlerNameByImport(moduleName)
            if not bundleName:
                msg = 'for module ' + moduleName
                self.warning('No bundle %s' % msg)
                raise errors.NoBundleError(msg)
            else:
                bundleNames.append(bundleName)

        deps = []
        for bundleName in bundleNames:
            thisdeps = basket.getDependencies(bundleName)
            self.debug('dependencies of %s: %r' % (bundleName, thisdeps[1:]))
            deps.extend(thisdeps)

        sums = []
        for dep in deps:
            bundler = basket.getBundlerByName(dep)
            if not bundler:
                self.warning('Did not find bundle with name %s' % dep)
            else:
                sums.append((dep, bundler.bundle().md5sum))

        self.debug('requested bundles: %r' % [x[0] for x in sums])
        return sums

    def perspective_getBundleSumsByFile(self, filename):
        """
        Get a list of (bundleName, md5sum) of all dependency bundles,
        starting with this bundle, in the correct order.

        @param filename: the name of the file in a bundle
        @type  filename: str

        @returns: list of (bundleName, md5sum) tuples
        @rtype:   list of (str, str) tuples
        """
        self.debug('asked to get bundle sums for file %s' % filename)
        basket = self.vishnu.getBundlerBasket()
        bundleName = basket.getBundlerNameByFile(filename)
        if not bundleName:
            self.warning('Did not find a bundle for file %s' % filename)
            raise errors.NoBundleError("for file %s" % filename)

        return self.perspective_getBundleSums(bundleName)

    def perspective_getBundleZips(self, bundles):
        """
        Get the zip files for the given list of bundles.

        @param bundles: the names of the bundles to get
        @type  bundles: list of str

        @returns: dictionary of bundleName -> zipdata
        @rtype:   dict of str -> str
        """
        basket = self.vishnu.getBundlerBasket()
        zips = {}
        for name in bundles:
            bundler = basket.getBundlerByName(name)
            if not bundler:
                raise errors.NoBundleError(
                    'The bundle named "%s" was not found' % (name, ))
            zips[name] = bundler.bundle().getZip()
        return zips

    def perspective_authenticate(self, bouncerName, keycard):
        """
        Authenticate the given keycard.
        If no bouncerName given, authenticate against the manager's bouncer.
        If a bouncerName is given, authenticate against the given bouncer
        in the atmosphere.

        @since: 0.3.1

        @param bouncerName: the name of the atmosphere bouncer, or None
        @type  bouncerName: str or None
        @param keycard:     the keycard to authenticate
        @type  keycard:     L{flumotion.common.keycards.Keycard}

        @returns: a deferred, returning the keycard or None.
        """
        if not bouncerName:
            self.debug(
                'asked to authenticate keycard %r using manager bouncer' %
                    keycard)
            return self.vishnu.bouncer.authenticate(keycard)

        self.debug('asked to authenticate keycard %r using bouncer %s' % (
            keycard, bouncerName))
        avatarId = common.componentId('atmosphere', bouncerName)
        if not self.heaven.hasAvatar(avatarId):
            self.warning('No bouncer with id %s registered' % avatarId)
            raise errors.UnknownComponentError(avatarId)

        bouncerAvatar = self.heaven.getAvatar(avatarId)
        return bouncerAvatar.authenticate(keycard)

    def perspective_keepAlive(self, bouncerName, issuerName, ttl):
        """
        Resets the expiry timeout for keycards issued by issuerName. See
        L{flumotion.component.bouncers.bouncer} for more information.

        @since: 0.4.3

        @param bouncerName: the name of the atmosphere bouncer, or None
        @type  bouncerName: str or None
        @param issuerName: the issuer for which keycards should be kept
                           alive; that is to say, keycards with the
                           attribute 'issuerName' set to this value will
                           have their ttl values reset.
        @type  issuerName: str
        @param ttl: the new expiry timeout
        @type  ttl: number

        @returns: a deferred which will fire success or failure.
        """
        self.debug('keycards keepAlive on behalf of %s, ttl=%d',
                   issuerName, ttl)

        if not bouncerName:
            return self.vishnu.bouncer.keepAlive(issuerName, ttl)

        self.debug('looking for bouncer %s in atmosphere', bouncerName)
        avatarId = common.componentId('atmosphere', bouncerName)
        if not self.heaven.hasAvatar(avatarId):
            self.warning('No bouncer with id %s registered', avatarId)
            raise errors.UnknownComponentError(avatarId)

        bouncerAvatar = self.heaven.getAvatar(avatarId)
        return bouncerAvatar.keepAlive(issuerName, ttl)

    def perspective_getKeycardClasses(self):
        """
        Get the keycard classes the manager's bouncer can authenticate.

        @since: 0.3.1

        @returns: a deferred, returning a list of keycard class names
        @rtype:   L{twisted.internet.defer.Deferred} firing list of str
        """
        classes = self.vishnu.bouncer.keycardClasses
        return [reflect.qual(c) for c in classes]


class ManagerHeaven(pb.Root, log.Loggable):
    """
    I am a base class for heavens in the manager.

    @cvar avatarClass: the class object this heaven instantiates avatars from.
                       To be set in subclass.
    @ivar avatars:     a dict of avatarId -> Avatar
    @type avatars:     dict of str -> L{ManagerAvatar}
    @ivar vishnu:      the Vishnu in control of all the heavens
    @type vishnu:      L{flumotion.manager.manager.Vishnu}
    """
    avatarClass = None

    def __init__(self, vishnu):
        """
        @param vishnu: the Vishnu in control of all the heavens
        @type  vishnu: L{flumotion.manager.manager.Vishnu}
        """
        self.vishnu = vishnu
        self.avatars = {} # avatarId -> avatar; populated by
                          # manager.Dispatcher

    ### ManagerHeaven methods

    def getAvatar(self, avatarId):
        """
        Get the avatar with the given id.

        @param avatarId: id of the avatar to get
        @type  avatarId: str

        @returns: the avatar with the given id
        @rtype:   L{ManagerAvatar}
        """
        return self.avatars[avatarId]

    def hasAvatar(self, avatarId):
        """
        Check if a component with that name is registered.

        @param avatarId: id of the avatar to check
        @type  avatarId: str

        @returns: True if an avatar with that id is registered
        @rtype:   bool
        """
        return avatarId in self.avatars

    def getAvatars(self):
        """
        Get all avatars in this heaven.

        @returns: a list of all avatars in this heaven
        @rtype:   list of L{ManagerAvatar}
        """
        return self.avatars.values()
