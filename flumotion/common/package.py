# -*- Mode: Python; test-case-name: flumotion.test.test_common_package -*-
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

"""objects and functions used in dealing with packages
"""

import ihooks
import glob
import os
import sys

from twisted.python import rebuild, reflect

from flumotion.common import log, common
from flumotion.configure import configure

__version__ = "$Rev$"


class _PatchedModuleImporter(ihooks.ModuleImporter):
    """
    I am overriding ihook's ModuleImporter's import_module() method to
    accept (and ignore) the 'level' keyword argument that appeared in
    the built-in __import__() function in python2.5.

    While no built-in modules in python2.5 seem to use that keyword
    argument, 'encodings' module in python2.6 does and so it breaks if
    used together with ihooks.

    I make no attempt to properly support the 'level' argument -
    ihooks didn't make it into py3k, and the only use in python2.6
    we've seen so far, in 'encodings', serves as a performance hint
    and it seems that can be ignored with no difference in behaviour.
    """

    def import_module(self, name, globals=None, locals=None, fromlist=None,
                      level=-1):
        # all we do is drop 'level' as ihooks don't support it, anyway
        return ihooks.ModuleImporter.import_module(self, name, globals,
                                                   locals, fromlist)


class PackageHooks(ihooks.Hooks):
    """
    I am an import Hooks object that makes sure that every package that gets
    loaded has every necessary path in the module's __path__ list.

    @type  packager: L{Packager}
    """
    packager = None

    def load_package(self, name, filename, file=None):
        # this is only ever called the first time a package is imported
        log.log('packager', 'load_package %s' % name)
        ret = ihooks.Hooks.load_package(self, name, filename, file)

        m = sys.modules[name]

        packagePaths = self.packager.getPathsForPackage(name)
        if not packagePaths:
            return ret

        # get full paths to the package
        paths = [os.path.join(path, name.replace('.', os.sep))
                 for path in packagePaths]
        for path in paths:
            if not path in m.__path__:
                log.log('packager', 'adding path %s for package %s' % (
                    path, name))
                m.__path__.append(path)

        return ret


class Packager(log.Loggable):
    """
    I am an object through which package paths can be registered, to support
    the partitioning of the module import namespace across bundles.
    """

    logCategory = 'packager'

    def __init__(self):
        self._paths = {} # key -> package path registered with that key
        self._packages = {} # package name -> keys for that package
        self.install()

    def install(self):
        """
        Install our custom importer that uses bundled packages.
        """
        self.debug('installing custom importer')
        self._hooks = PackageHooks()
        self._hooks.packager = self
        if sys.version_info < (2, 6):
            self._importer = ihooks.ModuleImporter()
        else:
            self.debug('python2.6 or later detected - using patched'
                       ' ModuleImporter')
            self._importer = _PatchedModuleImporter()
        self._importer.set_hooks(self._hooks)
        self._importer.install()

    def getPathsForPackage(self, packageName):
        """
        Return all absolute paths to the top level of a tree from which
        (part of) the given package name can be imported.
        """
        if packageName not in self._packages:
            return None

        return [self._paths[key] for key in self._packages[packageName]]

    def registerPackagePath(self, packagePath, key, prefix=configure.PACKAGE):
        """
        Register a given path as a path that can be imported from.
        Used to support partition of bundled code or import code from various
        uninstalled location.

        sys.path will also be changed to include this, and remove references
        to older packagePath's for the same bundle.

        @param packagePath: path to add under which the module namespaces live,
                            (ending in an md5sum, for flumotion purposes)
        @type  packagePath: string
        @param key          a unique id for the package being registered
        @type  key:         string
        @param prefix:      prefix of the packages to be considered
        @type  prefix:      string
        """

        new = True
        packagePath = os.path.abspath(packagePath)
        if not os.path.exists(packagePath):
            log.warning('bundle',
                'registering a non-existing package path %s' % packagePath)

        self.log('registering packagePath %s' % packagePath)

        # check if a packagePath for this bundle was already registered
        if key in self._paths:
            oldPath = self._paths[key]
            if packagePath == oldPath:
                self.log('already registered %s for key %s' % (
                    packagePath, key))
                return
            new = False

        # Find the packages in the path and sort them,
        # the following algorithm only works if they're sorted.
        # By sorting the list we can ensure that a parent package
        # is always processed before one of its children
        if not os.path.isdir(packagePath):
            log.warning('bundle', 'package path not a dir: %s',
                        packagePath)
            packageNames = []
        else:
            packageNames = _findPackageCandidates(packagePath, prefix)

        if not packageNames:
            log.log('bundle',
                'packagePath %s does not have candidates starting with %s' %
                    (packagePath, prefix))
            return
        packageNames.sort()

        self.log('package candidates %r' % packageNames)

        if not new:
            # it already existed, and now it's a different path
            log.log('bundle',
                'replacing old path %s with new path %s for key %s' % (
                    oldPath, packagePath, key))

            if oldPath in sys.path:
                log.log('bundle',
                    'removing old packagePath %s from sys.path' % oldPath)
                sys.path.remove(oldPath)

            # clear this key from our name -> key cache
            for keys in self._packages.values():
                if key in keys:
                    keys.remove(key)

        self._paths[key] = packagePath

        # put packagePath at the top of sys.path if not in there
        if not packagePath in sys.path:
            self.log('adding packagePath %s to sys.path' % packagePath)
            sys.path.insert(0, packagePath)

        # update our name->keys cache
        for name in packageNames:
            if name not in self._packages:
                self._packages[name] = [key]
            else:
                self._packages[name].insert(0, key)

        self.log('packagePath %s has packageNames %r' % (
            packagePath, packageNames))
        # since we want sub-modules to be fixed up before parent packages,
        # we reverse the list
        packageNames.reverse()

        for packageName in packageNames:
            if packageName not in sys.modules:
                continue
            self.log('fixing up %s ...' % packageName)

            # the package is imported, so mess with __path__ and rebuild
            package = sys.modules.get(packageName)
            for path in package.__path__:
                if not new and path.startswith(oldPath):
                    self.log('%s.__path__ before remove %r' % (
                        packageName, package.__path__))
                    self.log('removing old %s from %s.__path__' % (
                        path, name))
                    package.__path__.remove(path)
                    self.log('%s.__path__ after remove %r' % (
                        packageName, package.__path__))

            # move the new path to the top
            # insert at front because FLU_REGISTRY_PATH paths should override
            # base components, and because subsequent reload() should prefer
            # the latest registered path
            newPath = os.path.join(packagePath,
                                   packageName.replace('.', os.sep))

            # if path already at position 0, everything's fine
            # if it's in there at another place, it needs to move to front
            # if not in there, it needs to be put in front
            if len(package.__path__) == 0:
                # FIXME: this seems to happen to e.g. flumotion.component.base
                # even when it was just rebuilt and had the __path__ set
                # can be triggered by choosing a admin_gtk depending on
                # the base admin_gtk where the base admin_gtk changes
                self.debug('WARN: package %s does not have __path__ values' % (
                    packageName))
            elif package.__path__[0] == newPath:
                self.log('path %s already at start of %s.__path__' % (
                    newPath, packageName))
                continue

            if newPath in package.__path__:
                package.__path__.remove(newPath)
                self.log('moving %s to front of %s.__path__' % (
                    newPath, packageName))
            else:
                self.log('inserting new %s into %s.__path__' % (
                    newPath, packageName))
            package.__path__.insert(0, newPath)

            # Rebuilding these packages just to get __path__ fixed in
            # seems not necessary - but re-enable it if it breaks
            # self.log('rebuilding package %s from paths %r' % (packageName,
            #     package.__path__))
            # rebuild.rebuild(package)
            # self.log('rebuilt package %s with paths %r' % (packageName,
            #     package.__path__))
            self.log('fixed up %s, __path__ %s ...' % (
                packageName, package.__path__))

        # now rebuild all non-package modules in this packagePath if this
        # is not a new package
        if not new:
            self.log('finding end module candidates')
            if not os.path.isdir(packagePath):
                log.warning('bundle', 'package path not a dir: %s',
                            path)
                moduleNames = []
            else:
                moduleNames = findEndModuleCandidates(packagePath, prefix)
            self.log('end module candidates to rebuild: %r' % moduleNames)
            for name in moduleNames:
                if name in sys.modules:
                    # fixme: isn't sys.modules[name] sufficient?
                    self.log("rebuilding non-package module %s" % name)
                    try:
                        module = reflect.namedAny(name)
                    except AttributeError:
                        log.warning('bundle',
                            "could not reflect non-package module %s" % name)
                        continue

                    if hasattr(module, '__path__'):
                        self.log('rebuilding module %s with paths %r' % (name,
                            module.__path__))
                    rebuild.rebuild(module)
                    #if paths:
                    #    module.__path__ = paths

        self.log('registered packagePath %s for key %s' % (packagePath, key))

    def unregister(self):
        """
        Unregister all previously registered package paths, and uninstall
        the custom importer.
        """
        for path in self._paths.values():
            if path in sys.path:
                self.log('removing packagePath %s from sys.path' % path)
                sys.path.remove(path)
        self._paths = {}
        self._packages = {}
        self.debug('uninstalling custom importer')
        self._importer.uninstall()


def _listDirRecursively(path):
    """
    I'm similar to os.listdir, but I work recursively and only return
    directories containing python code.

    @param path: the path
    @type  path: string
    """
    retval = []
    try:
        files = os.listdir(path)
    except OSError:
        pass
    else:
        for f in files:
            # this only adds directories since files are not returned
            p = os.path.join(path, f)
            if os.path.isdir(p) and f != '.svn':
                retval += _listDirRecursively(p)

    if glob.glob(os.path.join(path, '*.py*')):
        retval.append(path)

    return retval


def _listPyFileRecursively(path):
    """
    I'm similar to os.listdir, but I work recursively and only return
    files representing python non-package modules.

    @param path: the path
    @type  path: string

    @rtype:      list
    @returns:    list of files underneath the given path containing python code
    """
    retval = []

    # get all the dirs containing python code
    dirs = _listDirRecursively(path)

    for directory in dirs:
        pyfiles = glob.glob(os.path.join(directory, '*.py*'))
        dontkeep = glob.glob(os.path.join(directory, '*__init__.py*'))
        for f in dontkeep:
            if f in pyfiles:
                pyfiles.remove(f)

        retval.extend(pyfiles)

    return retval


def _findPackageCandidates(path, prefix=configure.PACKAGE):
    """
    I take a directory and return a list of candidate python packages
    under that directory that start with the given prefix.
    A package is a module containing modules; typically the directory
    with the same name as the package contains __init__.py

    @param path: the path
    @type  path: string
    """
    # this function also "guesses" candidate packages when __init__ is missing
    # so a bundle with only a subpackage is also detected
    dirs = _listDirRecursively(os.path.join(path, prefix))

    # chop off the base path to get a list of "relative" bundlespace paths
    bundlePaths = [x[len(path) + 1:] for x in dirs]

    # remove some common candidates, like .svn subdirs, or containing -
    bundlePaths = [path for path in bundlePaths if path.find('.svn') == -1]
    bundlePaths = [path for path in bundlePaths if path.find('-') == -1]

    # convert paths to module namespace
    bundlePackages = [".".join(x.split(os.path.sep)) for x in bundlePaths]

    # now make sure that all parent packages for each package are listed
    # as well
    packages = {}
    for name in bundlePackages:
        packages[name] = 1
        parts = name.split(".")
        build = None
        for p in parts:
            if not build:
                build = p
            else:
                build = build + "." + p
            packages[build] = 1

    bundlePackages = packages.keys()

    # sort them so that depending packages are after higher-up packages
    bundlePackages.sort()

    return bundlePackages


def findEndModuleCandidates(path, prefix=configure.PACKAGE):
    """
    I take a directory and return a list of candidate python end modules
    (i.e., non-package modules) for the given module prefix.

    @param path:   the path under which to search for end modules
    @type  path:   string
    @param prefix: module prefix to check candidates under
    @type  prefix: string
    """
    pathPrefix = "/".join(prefix.split("."))
    files = _listPyFileRecursively(os.path.join(path, pathPrefix))

    # chop off the base path to get a list of "relative" import space paths
    importPaths = [x[len(path) + 1:] for x in files]

    # remove some common candidates, like .svn subdirs, or containing -
    importPaths = [path for path in importPaths if path.find('.svn') == -1]
    importPaths = [path for path in importPaths if path.find('-') == -1]

    # convert paths to module namespace
    endModules = [common.pathToModuleName(x) for x in importPaths]

    # remove all not starting with prefix
    endModules = [module for module in endModules
                             if module and module.startswith(prefix)]

    # sort them so that depending packages are after higher-up packages
    endModules.sort()

    # make unique
    res = {}
    for b in endModules:
        res[b] = 1

    return res.keys()

# singleton factory function
__packager = None


def getPackager():
    """
    Return the (unique) packager.

    @rtype: L{Packager}
    """
    global __packager
    if not __packager:
        __packager = Packager()

    return __packager
