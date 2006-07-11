# -*- Mode: Python; test-case-name: flumotion.test.test_manager_common -*-
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
common classes and code to support manager-side objects
"""

from twisted.internet import reactor
from twisted.spread import pb
from twisted.python import failure

from flumotion.common import errors, interfaces, log, common

class ManagerAvatar(pb.Avatar, log.Loggable):
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
    def __init__(self, heaven, avatarId, remoteIdentity):
        """
        @param heaven:   the heaven this avatar is part of
        @type  heaven:   L{flumotion.manager.base.ManagerHeaven}
        @param avatarId: id of the avatar to create
        @type  avatarId: str
        @param remoteIdentity: manager-assigned identity object for this
        avatar
        @type  remoteIdentity: anything
        """
        self.heaven = heaven
        self.avatarId = avatarId
        self.logName = avatarId
        self.mind = None
        self.vishnu = heaven.vishnu
        self.remoteIdentity = remoteIdentity

        self.debug("created new Avatar with id %s" % avatarId)
        
    def hasRemoteReference(self):
        """
        Check if the avatar has a remote reference to the peer.

        @rtype: bool
        """
        return self.mind != None
    
    # FIXME: we probably need to return Failure objects when something is wrong
    def mindCallRemote(self, name, *args, **kwargs):
        """
        Call the given remote method.

        @param name: name of the remote method
        @type  name: str
        """
        if not self.hasRemoteReference():
            self.warning(
                "Can't call remote method %s, no mind, except a local Traceback"
                % name)
            return
        
        # we can't do a .debug here, since it will trigger a resend of the
        # debug message as well, causing infinite recursion !
        # self.debug('Calling remote method %s%r' % (name, args))
        if not hasattr(self.mind, 'callRemote'):
            self.error("mind %r does not implement callRemote" % self.mind)
            return
        try:
            d = self.mind.callRemote(name, *args, **kwargs)
        except pb.DeadReferenceError:
            self.warning("mind %s is a dead reference, removing" % self.mind)
            self.mind = None
            return
        except Exception, e:
            self.warning("Exception trying to remote call '%s': %s: %s" % (
                name, str(e.__class__), ", ".join(e.args)))
            return

        d.addErrback(self._mindCallRemoteErrback, name)
        # FIXME: is there some way we can register an errback as the
        # LAST to call as a general fallback ?
        return d

    def _mindCallRemoteErrback(self, f, name):
        if f.check(AttributeError):
            # FIXME: what if the code raised an actual AttributeError ?
            # file an issue for twisted
            # this was done and resolved, can't remember the number now
            self.warning("No such remote method '%s', or AttributeError "
                "while executing remote method" % name)
            return failure.Failure(errors.NoMethodError(name))

        self.debug("Failure on remote call %s: %r, %s" % (name,
             f, f.getErrorMessage()))
        return f

    def attached(self, mind):
        """
        Tell the avatar that the given mind has been attached.
        This gives the avatar a way to call remotely to the client that
        requested this avatar.
        This is scheduled by the portal after the client has logged in.

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        self.mind = mind
        transport = self.mind.broker.transport
        tarzan = transport.getHost()
        jane = transport.getPeer()
        if tarzan and jane:
            self.debug("PB client connection seen by me is from me %s to %s" % (
                common.addressGetHost(tarzan),
                common.addressGetHost(jane)))
        self.log('Client attached is mind %s' % mind)

    def detached(self, mind):
        """
        Tell the avatar that the peer's client referenced by the mind
        has detached.

        Called through the manager's PB logout trigger calling
        L{flumotion.manager.manager.Dispatcher.removeAvatar}

        @type mind: L{twisted.spread.pb.RemoteReference}
        """
        assert(self.mind == mind)
        self.debug('PB client from %s detached' % self.getClientAddress())
        self.mind = None
        self.log('Client detached is mind %s' % mind)

    def getClientAddress(self):
        """
        Get the IPv4 address of the machine the PB client is connecting from,
        as seen from the avatar.

        @returns:  the IPv4 address the client is coming from, or None.
        @rtype:   str or None
        """
        if self.mind:
            peer = self.mind.broker.transport.getPeer()
            # pre-Twisted 1.3.0 compatibility
            try:
                return peer.host
            except AttributeError:
                return peer[1]
                
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
                raise errors.NoBundleError('The bundle named "%s" was not found'
                                           % (name,))
            zips[name] = bundler.bundle().getZip()
        return zips

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
        self.avatars = {} # avatarId -> avatar
       
    ### ManagerHeaven methods
    def createAvatar(self, avatarId, remoteIdentity):
        """
        Create a new avatar and manage it.

        @param avatarId: id of the avatar to create
        @type  avatarId: str
        @param remoteIdentity: the manager-side representation of the
        remote identity
        @type  remoteIdentity: anything

        @returns: a new avatar for the client
        @rtype:   L{flumotion.manager.base.ManagerAvatar}
        """
        self.debug('creating new Avatar with name %s' % avatarId)
        if self.avatars.has_key(avatarId):
            raise errors.AlreadyConnectedError(avatarId)

        avatar = self.avatarClass(self, avatarId, remoteIdentity)
        
        self.avatars[avatarId] = avatar
        return avatar

    def removeAvatar(self, avatarId):
        """
        Stop managing the given avatar.

        @param avatarId: id of the avatar to remove
        @type  avatarId: str
        """
        self.debug('removing Avatar with id %s' % avatarId)
        del self.avatars[avatarId]
        
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
        return self.avatars.has_key(avatarId)

    def getAvatars(self):
        """
        Get all avatars in this heaven.

        @returns: a list of all avatars in this heaven
        @rtype:   list of L{ManagerAvatar}
        """
        return self.avatars.values()
