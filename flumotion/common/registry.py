# -*- Mode: Python; test-case-name: flumotion.test.test_registry -*-
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
parsing of registry, which holds component and bundle information
"""

import os
import stat
import errno

from xml.dom import minidom, Node
from xml.parsers import expat

from flumotion.common import common, log, package, bundle, errors, fxml
from flumotion.configure import configure

__all__ = ['ComponentRegistry', 'registry']

def _getMTime(file):
    return os.stat(file)[stat.ST_MTIME]

_istrue = fxml.istrue

class RegistryEntryComponent:
    """
    I represent a <component> entry in the registry
    """
    # RegistryEntryComponent has a constructor with a lot of arguments,
    # but that's ok here. Allow it through pychecker.
    __pychecker__ = 'maxargs=13'

    def __init__(self, filename, type, 
                 source, base, properties, files,
                 entries, eaters, feeders, needs_sync, clock_priority,
                 sockets):
        """
        @type properties:  dict of str -> L{RegistryEntryProperty}
        @param entries:    dict of type -> entry
        @type entries:     dict of str -> L{RegistryEntryEntry}
        @param sockets:    list of sockets supported by the element
        @type sockets:     list of L{RegistryEntrySocket}
        """
        self.filename = filename
        self.type = type
        self.source = source
        self.base = base
        self.properties = properties
        self.files = files
        self.entries = entries
        self.eaters = eaters
        self.feeders = feeders
        self.needs_sync = needs_sync
        self.clock_priority = clock_priority
        self.sockets = sockets
        
    def getProperties(self):
        """
        Get a list of all properties.

        @rtype: list of L{RegistryEntryProperty}
        """
        return self.properties.values()

    def hasProperty(self, name):
        """
        Check if the component has a property with the given name.
        """
        return name in self.properties.keys()

    def getFiles(self):
        return self.files

    def getEntries(self):
        return self.entries.values()

    def getEntryByType(self, type):
        """
        Get the entry point for the given type of entry.

        @type type: string
        """
        return self.entries[type]
    
    def getGUIEntry(self):
        if not self.files:
            return
        
        # FIXME: Handle multiple files
        if len(self.files) > 1:
            return
        
        return self.files[0].getFilename()
    
    def getType(self):
        return self.type

    def getBase(self):
        return self.base

    def getSource(self):
        return self.source
    
    def getEaters(self):
        return self.eaters

    def getFeeders(self):
        return self.feeders

    def getNeedsSynchronization(self):
        return self.needs_sync

    def getClockPriority(self):
        return self.clock_priority

    def getSockets(self):
        return self.sockets

class RegistryEntryPlug:
    """
    I represent an <plug> entry in the registry
    """

    def __init__(self, filename, type, socket, entry, properties):
        """
        @type properties:  dict of str -> L{RegistryEntryProperty}
        @type entry:     L{RegistryEntryEntry}
        """
        self.filename = filename
        self.type = type
        self.socket = socket
        self.entry = entry
        self.properties = properties
        
    def getProperties(self):
        """
        Get a list of all properties.

        @rtype: list of L{RegistryEntryProperty}
        """
        return self.properties.values()

    def hasProperty(self, name):
        """
        Check if the component has a property with the given name.
        """
        return name in self.properties.keys()

    def getEntry(self):
        return self.entry

    def getType(self):
        return self.type

    def getSocket(self):
        return self.socket

class RegistryEntryBundle:
    "This class represents a <bundle> entry in the registry"
    def __init__(self, name, project, under, dependencies, directories):
        self.name = name
        self.project = project
        self.under = under
        self.dependencies = dependencies
        self.directories = directories

    def __repr__(self):
        return '<Bundle name=%s>' % self.name
    
    def getName(self):
        return self.name

    def getDependencies(self):
        return self.dependencies

    def getDirectories(self):
        return self.directories
    
    def getProject(self):
        return self.project

    def getBaseDir(self):
        if self.project == 'flumotion':
            return getattr(configure, self.under)

        from flumotion.project import project
        return project.get(self.project, self.under)
    
class RegistryEntryBundleDirectory:
    "This class represents a <directory> entry in the registry"
    def __init__(self, name, files):
        self.name = name
        self.files = files

    def getName(self):
        return self.name

    def getFiles(self):
        return self.files
    
class RegistryEntryBundleFilename:
    "This class represents a <filename> entry in the registry"
    def __init__(self, location, relative):
        self.location = location
        self.relative = relative

    def getLocation(self):
        return self.location

    def getRelative(self):
        return self.relative

class RegistryEntryProperty:
    "This class represents a <property> entry in the registry"
    def __init__(self, name, type, required=False, multiple=False):
        self.name = name
        self.type = type
        self.required = required
        self.multiple = multiple

    def __repr__(self):
        return '<Property name=%s>' % self.name
    
    def getName(self):
        return self.name

    def getType(self):
        return self.type
    
    def isRequired(self):
        return self.required

    def isMultiple(self):
        return self.multiple

class RegistryEntryFile:
    "This class represents a <file> entry in the registry"
    def __init__(self, filename, type):
        self.filename = filename
        self.type = type

    def getName(self):
        return os.path.basename(self.filename)

    def getType(self):
        return self.type
    
    def getFilename(self):
        return self.filename

    def isType(self, type):
        return self.type == type
    
class RegistryEntryEntry:
    "This class represents a <entry> entry in the registry"
    def __init__(self, type, location, function):
        self.type = type
        self.location = location
        self.function = function

    def getType(self):
        return self.type

    def getLocation(self):
        return self.location

    def getModuleName(self, base=None):
        if base:
            path = os.path.join(base, self.getLocation())
        else:
            path = self.getLocation()
        return common.pathToModuleName(path)

    def getFunction(self):
        return self.function
    
class RegistryEntryEater:
    "This class represents a <eater> entry in the registry"
    def __init__(self, name, required=True, multiple=False):
        self.name = name
        self.required = required
        self.multiple = multiple

    def getName(self):
        return self.name

    def getRequired(self):
        return self.required

    def getMultiple(self):
        return self.multiple
    
class RegistryEntrySocket(str):
    pass

class RegistryParser(fxml.Parser):
    """
    Registry parser

    I have two modes, one to parse registries and another one to parse
    standalone component files.

    For parsing registries use the parseRegistry function and for components
    use parseRegistryFile.

    I also have a list of all components and directories which the
    directory use (instead of saving its own copy)
    """
    
    def __init__(self):
        self.clean()
        
    def clean(self):
        self._components = {}
        self._directories = {}
        self._bundles = {}
        self._plugs = {}
        
    def getComponents(self):
        return self._components.values()

    def getComponent(self, name):
        return self._components[name]

    def getPlugs(self):
        return self._plugs.values()

    def getPlug(self, name):
        return self._plugs[name]

    def _parseComponents(self, node):
        # <components>
        #   <component>
        # </components>
        
        components = {}
        def addComponent(comp):
            components[comp.getType()] = comp
        
        parsers = {'component': (self._parseComponent, addComponent)}
        self.parseFromTable(node, parsers)

        return components
    
    def _parseComponent(self, node):
        # <component type="..." base="...">
        #   <source>
        #   <eater>
        #   <feeder>
        #   <properties>
        #   <entries>
        #   <synchronization>
        #   <sockets>
        # </component>
        
        #FIXME: make sure base is in all components
        type, baseDir = self.parseAttributes(node, ('type',), ('base',))

        files = []
        source = fxml.Box(None)
        entries = {}
        eaters = []
        feeders = []
        synchronization = fxml.Box((False, 100))
        sockets = []
        properties = {}

        # Merge in options for inherit
        if node.hasAttribute('inherit'):
            base_type = str(node.getAttribute('inherit'))
            base = self.getComponent(base_type)
            for prop in base.getProperties():
                properties[prop.getName()] = prop

        parsers = {'source': (self._parseSource, source.set),
                   'properties': (self._parseProperties, properties.update),
                   'files': (self._parseFiles, files.extend),
                   'entries': (self._parseEntries, entries.update),
                   'eater': (self._parseEater, eaters.append),
                   'feeder': (self._parseFeeder, feeders.append),
                   'synchronization': (self._parseSynchronization,
                                       synchronization.set),
                   'sockets': (self._parseSockets, sockets.extend)}

        self.parseFromTable(node, parsers)

        source = source.unbox()
        needs_sync, clock_priority = synchronization.unbox()

        return RegistryEntryComponent(self.filename,
                                      type, source, baseDir,
                                      properties, files,
                                      entries, eaters, feeders,
                                      needs_sync, clock_priority,
                                      sockets)

    def _parseSource(self, node):
        # <source location="..."/>
        location, = self.parseAttributes(node, ('location',))
        return location

    def _parseProperty(self, node):
        # <property name="..." type="" required="yes/no" multiple="yes/no"/>
        # returns: RegistryEntryProperty

        attrs = self.parseAttributes(node, ('name', 'type'),
                                     ('required', 'multiple'))
        name, type, required, multiple = attrs
        required = _istrue(required)
        multiple = _istrue(multiple)
        return RegistryEntryProperty(name, type, required=required,
                                     multiple=multiple)

    def _parseProperties(self, node):
        # <properties>
        #   <property>
        # </properties>
        
        properties = {}
        def addProperty(prop):
            properties[prop.getName()] = prop

        parsers = {'property': (self._parseProperty, addProperty)}

        self.parseFromTable(node, parsers)

        return properties

    def _parseFile(self, node):
        # <file name="..." type=""/>
        # returns: RegistryEntryFile

        name, type = self.parseAttributes(node, ('name', 'type'))
        dir = os.path.split(self.filename)[0]
        filename = os.path.join(dir, name)
        return RegistryEntryFile(filename, type)

    def _parseFiles(self, node):
        # <files>
        #   <file>
        # </files>

        files = []
        parsers = {'file': (self._parseFile, files.append)}

        self.parseFromTable(node, parsers)

        return files

    def _parseSocket(self, node):
        # <socket type=""/>
        # returns: RegistryEntrySocket

        type, = self.parseAttributes(node, ('type',))
        return RegistryEntrySocket(type)

    def _parseSockets(self, node):
        # <sockets>
        #   <socket>
        # </sockets>

        sockets = []
        parsers = {'socket': (self._parseSocket, sockets.append)}

        self.parseFromTable(node, parsers)

        return sockets

    def _parseEntry(self, node):
        attrs = self.parseAttributes(node, ('type', 'location', 'function'))
        type, location, function = attrs
        return RegistryEntryEntry(type, location, function)

    def _parseEntries(self, node):
        # <entries>
        #   <entry>
        # </entries>
        # returns: dict of type -> entry

        entries = {}
        def addEntry(entry):
            if entry.getType() in entries:
                raise XmlParserError("entry %s already specified"
                                     % entry.getType())
            entries[entry.getType()] = entry

        parsers = {'entry': (self._parseEntry, addEntry)}

        self.parseFromTable(node, parsers)

        return entries

    def _parseEater(self, node):
        # <eater name="..." [required="yes/no"] [multiple="yes/no"]/>
        attrs = self.parseAttributes(node, ('name',), ('required', 'multiple'))
        name, required, multiple = attrs
        # only required defaults to True
        required = _istrue(required or 'True')
        multiple = _istrue(multiple)

        return RegistryEntryEater(name, required, multiple)

    def _parseFeeder(self, node):
        # <feeder name="..."/>
        name, = self.parseAttributes(node, ('name',))
        return name

    def _parseSynchronization(self, node):
        # <synchronization [required="yes/no"] [clock-priority="100"]/>
        attrs = self.parseAttributes(node, (), ('required', 'clock-priority'))
        required, clock_priority = attrs
        required = _istrue(required)
        clock_priority = int(clock_priority or '100')
        return required, clock_priority

    def _parsePlugEntry(self, node):
        # <entry location="" function=""/>
        # returns: RegistryEntryEntry

        attrs = self.parseAttributes(node, ('location', 'function'))
        location, function = attrs
        return RegistryEntryEntry('plug', location, function)

    def _parsePlug(self, node):
        # <plug socket="..." type="...">
        #   <entry>
        #   <properties>
        # </plug>
        
        type, socket = self.parseAttributes(node, ('type', 'socket'))

        entry = fxml.Box(None)
        properties = {}

        parsers = {'entry': (self._parsePlugEntry, entry.set),
                   'properties': (self._parseProperties, properties.update)}

        self.parseFromTable(node, parsers)

        if not entry.unbox():
            raise XmlParserError("<plug> %s needs an <entry>" % type)

        return RegistryEntryPlug(self.filename, type,
                                 socket, entry.unbox(), properties)

    def _parsePlugs(self, node):
        # <plugs>
        #   <plug>
        # </plugs>
        
        self.checkAttributes(node)

        plugs = {}
        def addPlug(plug):
            plugs[plug.getType()] = plug

        parsers = {'plug': (self._parsePlug, addPlug)}
        self.parseFromTable(node, parsers)

        return plugs
    
    ## Component registry specific functions
    def parseRegistryFile(self, filename, string=None):
        # FIXME: better separation of filename and string ?
        """
        Parse the given XML registry part file,
        And add it to our registry.
        If a string is given, the string overrides the given file.
        """
        self.filename = filename
        # so we have something nice to print for parsing errors
        if string:
            self.filename = "<string>"

        root = self.getRoot(self.filename, string)
        node = root.documentElement

        if node.nodeName != 'registry':
            # ignore silently, since this function is used to parse all
            # .xml files encountered
            self.debug('%s does not have registry as root tag' % self.filename)
            return

        # shouldn't have <directories> elements in registry fragments
        self._parseRoot(node, disallowed=['directories'])

    def _parseBundles(self, node):
        # <bundles>
        #   <bundle>
        # </bundles>
        
        bundles = {}
        def addBundle(bundle):
            bundles[bundle.getName()] = bundle

        parsers = {'bundle': (self._parseBundle, addBundle)}
        self.parseFromTable(node, parsers)

        return bundles
    
    def _parseBundle(self, node):
        # <bundle name="...">
        #   <dependencies>
        #   <directories>
        # </bundle>
        
        attrs = self.parseAttributes(node, ('name',), ('project', 'under'))
        name, project, under = attrs
        project = project or 'flumotion'
        under = under or 'pythondir'

        dependencies = []
        directories = []

        parsers = {'dependencies': (self._parseBundleDependencies,
                                    dependencies.extend),
                   'directories': (self._parseBundleDirectories,
                                   directories.extend)}
        self.parseFromTable(node, parsers)

        return RegistryEntryBundle(name, project, under, dependencies, directories)

    def _parseBundleDependency(self, node):
        name, = self.parseAttributes(node, ('name',))
        return name

    def _parseBundleDependencies(self, node):
        # <dependencies>
        #   <dependency name="">
        # </dependencies>
        dependencies = []

        parsers = {'dependency': (self._parseBundleDependency,
                                  dependencies.append)}
        self.parseFromTable(node, parsers)
            
        return dependencies

    def _parseBundleDirectories(self, node):
        # <directories>
        #   <directory>
        # </directories>
        directories = []

        parsers = {'directory': (self._parseBundleDirectory,
                                 directories.append)}
        self.parseFromTable(node, parsers)
            
        return directories

    def _parseBundleDirectoryFilename(self, node, name):
        attrs = self.parseAttributes(node, ('location',), ('relative',))
        location, relative = attrs
            
        if not relative:
            relative = os.path.join(name, location)
                
        return RegistryEntryBundleFilename(location, relative)

    def _parseBundleDirectory(self, node):
        # <directory name="">
        #   <filename location="" [ relative="" ] >
        # </directory>
        name, = self.parseAttributes(node, ('name',))

        filenames = []
        def parseFilename(node):
            return self._parseBundleDirectoryFilename(node, name)

        parsers = {'filename': (parseFilename, filenames.append)}
        self.parseFromTable(node, parsers)

        return RegistryEntryBundleDirectory(name, filenames)

    ## Base registry specific functions
    def parseRegistry(self, filename, string=None):
        self.filename = filename

        root = self.getRoot(filename, string)
        self._parseRoot(root.documentElement)

    def getDirectories(self):
        return self._directories.values()

    def getDirectory(self, name):
        return self._directories[name]

    def addDirectory(self, directory):
        """
        Add a registry path object to the parser.

        @type directory: {RegistryDirectory}
        """
        self._directories[directory.getPath()] = directory

    def _parseRoot(self, node, disallowed=None):
        # <components>...</components>*
        # <plugs>...</plugs>*
        # <directories>...</directories>*
        # <bundles>...</bundles>*
        parsers = {'components': (self._parseComponents,
                                  self._components.update),
                   'directories': (self._parseDirectories,
                                   self._directories.update),
                   'bundles': (self._parseBundles, self._bundles.update),
                   'plugs': (self._parsePlugs, self._plugs.update)}

        self.parseFromTable(node, parsers)
        
    def _parseDirectories(self, node): 
        # <directories>
        #   <directory>
        # </directories>
        
        directories = {}
        def addDirectory(d):
            directories[d.getPath()] = d
        
        parsers = {'directory': (self._parseDirectory, addDirectory)}
        self.parseFromTable(node, parsers)

        return directories

    def _parseDirectory(self, node):
        # <directory filename="..."/>
        filename, = self.parseAttributes(node, ('filename',))
        return RegistryDirectory(filename)

    
# FIXME: filename -> path
class RegistryDirectory:
    """
    I represent a directory under a path managed by the registry.
    I can be queried for a list of partial registry .xml files underneath
    the given path, under the given prefix.
    """
    def __init__(self, path, prefix='flumotion'):
        self._path = path
        self._prefix = prefix
        self._files = self._getFileList(os.path.join(path, prefix))
        
    def _getFileList(self, root):
        """
        Get all files ending in .xml from all directories under the given root.

        @type  root: string
        @param root: the root directory under which to search
        
        @returns: a list of .xml files, relative to the given root directory
        """

        files = []
        
        if os.path.exists(root):
            try:
                directory_files = os.listdir(root)
            except OSError, e:
                if e.errno == errno.EACCES:
                    return files
                else:
                    raise
                
            for dir in directory_files:
                filename = os.path.join(root, dir)
                # if it's a .xml file, then add it to the list
                if not os.path.isdir(filename):
                    if filename.endswith('.xml'):
                        files.append(filename)
                # if it's a directory, then get its files and add them
                else:
                    files += self._getFileList(filename)
                
        return files

    def lastModified(self):
        return max(map(_getMTime, self._files))

    def getFiles(self):
        """
        Return a list of all .xml registry files underneath this registry
        path.
        """
        return self._files

    def getPath(self):
        return self._path
    
class ComponentRegistry(log.Loggable):
    """Registry, this is normally not instantiated."""
    
    logCategory = 'registry'
    filename = os.path.join(configure.registrydir, 'registry.xml')

    def __init__(self):
        self._parser = RegistryParser()

        if (os.path.exists(self.filename) and
            os.access(self.filename, os.R_OK)):
            self.info('Parsing registry: %s' % self.filename)
            self._parser.parseRegistry(self.filename)

        self.verify()
    
    def addFile(self, filename, string=None):
        if filename.endswith('registry.xml'):
            self.warning('%s seems to be an old registry in your tree, please remove it' % filename) 
        self.debug('Adding file: %s' % filename)
        self._parser.parseRegistryFile(filename, string)
        
    def addFromString(self, string):
        self.addFile('<string>', string)
        
    def addRegistryPath(self, path, prefix='flumotion', force=False):
        """
        Add a registry path to this registry.

        If force is False, the registry path will only be re-scanned
        if the directory has been modified since the last scan.
        If force is True, then the registry path will be parsed regardless
        of the modification time.

        @param path: a full path containing a 'flumotion' directory,
                     which will be scanned for registry files.
        """
        self.debug('path %s, prefix %s, force %r' % (path, prefix, force))
        if not os.path.exists(path):
            return

        directory = self._parser._directories.get(path, None)
        if not force and directory:
            # if directory is watched in the registry, and it hasn't been
            # updated, everything's fine
            dTime = directory.lastModified()
            fTime = _getMTime(self.filename)
            if dTime < fTime:
                self.debug('%s has not been changed since last registry parse' %
                    path)
                return
        
        # registry path was either not watched or updated, or a force was
        # asked, so reparse
        self.info('Scanning registry path %s' % path)
        registryPath = RegistryDirectory(path, prefix=prefix)
        files = registryPath.getFiles()
        self.debug('Found %d possible registry files' % len(files))
        map(self.addFile, files)
        
        self._parser.addDirectory(registryPath)
        
    def isEmpty(self):
        return len(self._parser._components) == 0

    def getComponent(self, name):
        """
        @rtype: L{RegistryEntryComponent}
        """
        return self._parser._components[name]

    def hasComponent(self, name):
        return self._parser._components.has_key(name)

    def getComponents(self):
        return self._parser._components.values()

    def getPlug(self, type):
        """
        @rtype: L{RegistryEntryPlug}
        """
        return self._parser._plugs[type]

    def hasPlug(self, name):
        return self._parser._plugs.has_key(name)

    def getPlugs(self):
        return self._parser._plugs.values()

    def getBundles(self):
        return self._parser._bundles.values()
        
    def getDirectories(self):
        return self._parser.getDirectories()

    def makeBundlerBasket(self):
        """
        @rtype: L{flumotion.common.bundle.BundlerBasket}
        """
        def load():
            ret = bundle.BundlerBasket()
            for b in self.getBundles():
                bundleName = b.getName()
                self.debug('Adding bundle %s' % bundleName)
                for d in b.getDirectories():
                    directory = d.getName()
                    for file in d.getFiles():
                        try:
                            basedir = b.getBaseDir()
                        except errors.NoProjectError, e:
                            self.warning("Could not find project %s" % e.args)
                            raise
                        fullpath = os.path.join(basedir, directory,
                                                file.getLocation())
                        relative = file.getRelative()
                        self.log('Adding path %s as %s to bundle %s' % (
                            fullpath, relative, bundleName))
                        try:
                            ret.add(bundleName, fullpath, relative)
                        except Exception, e:
                            self.debug("Reason: %r" % e)
                            raise RuntimeError(
                                'Could not add %s to bundle %s (%s)'
                                % (fullpath, bundleName, e))
                for d in b.getDependencies():
                    self.log('Adding dependency of %s on %s' % (bundleName, d))
                    ret.depend(bundleName, d)
            return ret

        try:
            return load()
        except Exception, e:
            self.warning("Bundle problem, rebuilding registry (%s)" % e)
            self.verify(force=True)
            try:
                return load()
            except Exception, e:
                self.debug("Could not register bundles twice: %s" %
                    log.getExceptionMessage(e))
                self.error("Could not not register bundles (%s)" % e)

    def dump(self, fd):
        """
        Dump the cache of components to the given opened file descriptor.

        @type  fd: integer
        @param fd: open file descriptor to write to
        """
        
        def w(i, msg):
            print >> fd, ' '*i + msg
            
        w(0, '<registry>')
        w(0, '')

        # Write components
        w(2, '<components>')
        w(0, '')
        for component in self.getComponents():
            w(4, '<component type="%s" base="%s">' % (component.getType(),
                component.getBase()))

            w(6, '<source location="%s"/>' % component.getSource())
            for x in component.getEaters():
                w(6, '<eater name="%s" required="%s" multiple="%s"/>'
                  % (x.getName(), x.getRequired() and "yes" or "no",
                     x.getMultiple() and "yes" or "no"))
            for x in component.getFeeders():
                w(6, '<feeder name="%s"/>' % x)
            w(6, '<synchronization required="%s" clock-priority="%d"/>'
              % (component.getNeedsSynchronization() and "yes" or "no",
                 component.getClockPriority()))

            sockets = component.getSockets()
            if sockets:
                w(6, '<sockets>')
                for socket in sockets:
                    w(8, '<socket type="%s"/>' % socket)
                w(6, '</sockets>')

            w(6, '<properties>')
            for prop in component.getProperties():
                w(8, '<property name="%s" type="%s" required="%s" multiple="%s"/>' % (
                    prop.getName(),
                    prop.getType(),
                    prop.isRequired(),
                    prop.isMultiple()))
            w(6, '</properties>')

            files = component.getFiles()
            if files:
                w(6, '<files>')
                for file in files:
                    w(8, '<file name="%s" type="%s"/>' % (
                        file.getName(),
                        file.getType()))
                w(6, '</files>')

            entries = component.getEntries()
            if entries:
                w(6, '<entries>')
                for entry in entries:
                    w(8, '<entry type="%s" location="%s" function="%s"/>' % (
                        entry.getType(),
                        entry.getLocation(),
                        entry.getFunction()))
                w(6, '</entries>')
            w(4, '</component>')
            w(0, '')
                
        w(2, '</components>')
        w(0, '')

        # Write plugs
        w(2, '<plugs>')
        w(0, '')
        for plug in self.getPlugs():
            w(4, '<plug type="%s" socket="%s">'
              % (plug.getType(), plug.getSocket()))

            entry = plug.getEntry()
            w(6, ('<entry location="%s" function="%s"/>'
                  % (entry.getLocation(), entry.getFunction())))

            w(6, '<properties>')
            for prop in plug.getProperties():
                w(8, ('<property name="%s" type="%s" required="%s" multiple="%s"/>'
                      % (prop.getName(),
                         prop.getType(),
                         prop.isRequired(),
                         prop.isMultiple())))
            w(6, '</properties>')

            w(4, '</plug>')
            w(0, '')
                
        w(2, '</plugs>')
        w(0, '')

        # bundles
        w(2, '<bundles>')
        for bundle in self.getBundles():
            w(4, '<bundle name="%s" project="%s">' % (
                bundle.getName(), bundle.getProject()))

            dependencies = bundle.getDependencies()
            if dependencies:
                w(6, '<dependencies>')
                for dependency in dependencies:
                    w(8, '<dependency name="%s"/>' % dependency)
                w(6, '</dependencies>')

            dirs = bundle.getDirectories()
            if dirs:
                w(6, '<directories>')
                for dir in dirs:
                    w(8, '<directory name="%s">' % dir.getName())
                    for filename in dir.getFiles():
                        w(10, '<filename location="%s" relative="%s"/>' % (
                            filename.getLocation(), filename.getRelative()))
                    w(8, '</directory>')
                w(6, '</directories>')
                
            w(4, '</bundle>')
            w(0, '')
        w(2, '</bundles>')


        # Directories
        directories = self.getDirectories()
        if directories:
            w(2, '<directories>')
            w(0, '')
            for d in directories:
                w(4, '<directory filename="%s"/>' % d.getPath())
            w(2, '</directories>')
            w(0, '')
        
        w(0, '</registry>')

    def clean(self):
        """
        Clean the cache of components.
        """
        self._parser.clean()

    def rebuildNeeded(self):
        if not os.path.exists(self.filename):
            return True
        
        registry_modified = _getMTime(self.filename)
        for d in self._parser.getDirectories():
            if d.lastModified() > registry_modified:
                return True

        return False
    
    def save(self, force=False):
        if not force and not self.rebuildNeeded():
            return
        
        self.info('Saving registry to %s' % self.filename)
        
        # create parent directory
        dir = os.path.split(self.filename)[0]
        if not os.path.exists(dir):
            try:
                os.makedirs(dir)
            except OSError, e:
                if e.errno == errno.EACCES:
                    self.error('Registry directory %s could not be created !' %
                        dir)
                else:
                    raise
                
        if not os.path.isdir(dir):
            self.error('Registry directory %s is not a directory !')
        try:
            fd = open(self.filename, 'w')
            self.dump(fd)
        except IOError, e:
            if e.errno == errno.EACCES:
                self.error('Registry file %s could not be created !' %
                    self.filename)
            else:
                raise

    def verify(self, force=False):
        """
        Verify if the registry is uptodate and rebuild if it is not.

        @param force: True if the registry needs rebuilding for sure.
        """
        # construct a list of all paths to scan for registry .xml files
        registryPaths = [configure.pythondir, ]
        if os.environ.has_key('FLU_PROJECT_PATH'):
            paths = os.environ['FLU_PROJECT_PATH']
            registryPaths += paths.split(':')
        
        # get the list of all paths used to construct the old registry
        oldRegistryPaths = [dir.getPath()
                                  for dir in self.getDirectories()]
        self.debug('previously scanned registry paths: %s' % 
            ", ".join(oldRegistryPaths))

        # if the lists are not equal, then a path was added or removed and
        # we need to rebuild
        registryPaths.sort()
        oldRegistryPaths.sort()
        if registryPaths != oldRegistryPaths:
            self.debug('old and new registry paths are different')
            self.info('Rescanning registry paths')
            force = True
        else:
            self.debug('registry paths are still the same')

        if force:
            self.clean()
        
        for directory in registryPaths:
            self.addRegistryPath(directory, force=force)

        self.save(force)

__registry = None

def getRegistry():
    """
    Return the registry.  Only one registry will ever be created.

    @rtype: L{ComponentRegistry}
    """
    global __registry

    if not __registry:
        log.debug('registry', 'instantiating registry')
        __registry = ComponentRegistry()

    return __registry
