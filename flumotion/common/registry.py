# -*- Mode: Python; test-case-name: flumotion.test.test_registry -*-
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
parsing of registry, which holds component and bundle information
"""

import os
import sets
import stat
import errno
from StringIO import StringIO

from xml.dom import minidom, Node
from xml.parsers import expat
from xml.sax import saxutils

from flumotion.common import common, log, package, bundle, errors, fxml
from flumotion.configure import configure

# Re-enable when reading the registry cache is lighter-weight, or we
# decide that it's a good idea, or something. See #799.
READ_CACHE = False

__all__ = ['ComponentRegistry', 'registry']

def _getMTime(file):
    return os.stat(file)[stat.ST_MTIME]

class RegistryEntryComponent:
    """
    I represent a <component> entry in the registry
    """
    # RegistryEntryComponent has a constructor with a lot of arguments,
    # but that's ok here. Allow it through pychecker.
    __pychecker__ = 'maxargs=14'

    def __init__(self, filename, type,
                 source, description, base, properties, files,
                 entries, eaters, feeders, needs_sync, clock_priority,
                 sockets):
        """
        @param filename:   name of the XML file this component is parsed from
        @type  filename:   str
        @param properties: dict of name -> property
        @type  properties: dict of str -> L{RegistryEntryProperty}
        @param entries:    dict of entry point type -> entry
        @type  entries:    dict of str -> L{RegistryEntryEntry}
        @param sockets:    list of sockets supported by the element
        @type  sockets:    list of str
        """
        self.filename = filename
        self.type = type
        self.source = source
        self.description = description
        # we don't want to end up with the string "None"
        if not self.description:
            self.description = ""
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

    def getDescription(self):
        return self.description

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
    I represent a <plug> entry in the registry
    """

    def __init__(self, filename, type, socket, entry, properties):
        """
        @param filename:   name of the XML file this plug is parsed from
        @type  filename:   str
        @param type:       the type of plug
        @type  type:       str
        @param socket:     the fully qualified class name of the socket this
                           plug can be plugged in to
        @type  socket:     str
        @param entry:      entry point for instantiating the plug
        @type  entry:      L{RegistryEntryEntry}
        @param properties: properties of the plug
        @type  properties: dict of str -> L{RegistryEntryProperty}
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

    def getUnder(self):
        return self.under

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
    def __init__(self, name, type, description, required=False, multiple=False):
        self.name = name
        self.type = type
        self.description = description
        # we don't want to end up with the string "None"
        if not self.description:
            self.description = ""
        self.required = required
        self.multiple = multiple

    def __repr__(self):
        return '<Property name=%s>' % self.name

    def getName(self):
        return self.name

    def getType(self):
        return self.type

    def getDescription(self):
        return self.description

    def isRequired(self):
        return self.required

    def isMultiple(self):
        return self.multiple

class RegistryEntryCompoundProperty(RegistryEntryProperty):
    "This class represents a <compound-property> entry in the registry"
    def __init__(self, name, description, properties, required=False,
                 multiple=False):
        RegistryEntryProperty.__init__(self, name, 'compound', description,
                                       required, multiple)
        self.properties = properties

    def __repr__(self):
        return '<Compound-property name=%s>' % self.name

    def getProperties(self):
        """
        Get a list of all sub-properties.

        @rtype: list of L{RegistryEntryProperty}
        """
        return self.properties.values()

    def hasProperty(self, name):
        """
        Check if the compound-property has a sub-property with the
        given name.
        """
        return name in self.properties

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

class RegistryParser(fxml.Parser):
    """
    Registry parser

    I have two modes, one to parse registries and another one to parse
    standalone component files.

    For parsing registries use the parseRegistry function and for components
    use parseRegistryFile.

    I also have a list of all components and directories which the
    registry uses (instead of saving its own copy)
    """

    def __init__(self):
        self.clean()

    def clean(self):
        self._components = {}
        self._directories = {} # path -> RegistryDirectory
        self._bundles = {}
        self._plugs = {}

    def getComponents(self):
        return self._components.values()

    def getComponent(self, name):
        try:
            return self._components[name]
        except KeyError:
            raise errors.UnknownComponentError("unknown component type:"
                                               " %s" % (name,))

    def getPlugs(self):
        return self._plugs.values()

    def getPlug(self, name):
        try:
            return self._plugs[name]
        except KeyError:
            raise errors.UnknownPlugError("unknown plug type: %s"
                                          % (name,))

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
        # <component type="..." base="..." description="...">
        #   <source>
        #   <eater>
        #   <feeder>
        #   <properties>
        #   <entries>
        #   <synchronization>
        #   <sockets>
        # </component>

        #FIXME: make sure base is in all components
        type, baseDir, description = self.parseAttributes(node,
            required=('type', ), optional=('base', 'description'))

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

        parsers = {
            'source':          (self._parseSource, source.set),
            'properties':      (self._parseProperties, properties.update),
            'files':           (self._parseFiles, files.extend),
            'entries':         (self._parseEntries, entries.update),
            'eater':           (self._parseEater, eaters.append),
            'feeder':          (self._parseFeeder, feeders.append),
            'synchronization': (self._parseSynchronization,
                                synchronization.set),
            'sockets':         (self._parseSockets, sockets.extend),
        }

        self.parseFromTable(node, parsers)

        source = source.unbox()
        needs_sync, clock_priority = synchronization.unbox()

        return RegistryEntryComponent(self.filename,
                                      type, source, description, baseDir,
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

        attrs = self.parseAttributes(node, required=('name', 'type'),
            optional=('required', 'multiple', 'description'))
        name, type, required, multiple, description = attrs
        required = common.strToBool(required)
        multiple = common.strToBool(multiple)
        return RegistryEntryProperty(name, type, description, required=required,
                                     multiple=multiple)

    def _parseCompoundProperty(self, node):
        # <compound-property name="..." required="yes/no" multiple="yes/no">
        #   <property ... />*
        #   <compound-property ... >...</compound-property>*
        # </compound-property>
        # returns: RegistryEntryCompoundProperty

        attrs = self.parseAttributes(node, required=('name',),
            optional=('required', 'multiple', 'description'))
        name, required, multiple, description = attrs
        required = common.strToBool(required)
        multiple = common.strToBool(multiple)

        properties = {}
        def addProperty(prop):
            properties[prop.getName()] = prop

        parsers = {'property': (self._parseProperty, addProperty),
                   'compound-property': (self._parseCompoundProperty,
                                         addProperty)}
        self.parseFromTable(node, parsers)

        return RegistryEntryCompoundProperty(name, description, properties,
                   required=required, multiple=multiple)

    def _parseProperties(self, node):
        # <properties>
        #   <property>*
        #   <compound-proerty>*
        # </properties>

        properties = {}
        def addProperty(prop):
            properties[prop.getName()] = prop

        parsers = {'property': (self._parseProperty, addProperty),
                   'compound-property': (self._parseCompoundProperty,
                                         addProperty)}

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
        # returns: str of the type

        type, = self.parseAttributes(node, ('type',))
        return type

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
                raise fxml.ParserError("entry %s already specified"
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
        required = common.strToBool(required or 'True')
        multiple = common.strToBool(multiple)

        return RegistryEntryEater(name, required, multiple)

    def _parseFeeder(self, node):
        # <feeder name="..."/>
        name, = self.parseAttributes(node, ('name',))
        return name

    def _parseSynchronization(self, node):
        # <synchronization [required="yes/no"] [clock-priority="100"]/>
        attrs = self.parseAttributes(node, (), ('required', 'clock-priority'))
        required, clock_priority = attrs
        required = common.strToBool(required)
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
            raise fxml.ParserError("<plug> %s needs an <entry>" % type)

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
    def parseRegistryFile(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        self.filename = getattr(file, 'name', '<string>')
        root = self.getRoot(file)
        node = root.documentElement

        if node.nodeName != 'registry':
            # ignore silently, since this function is used to parse all
            # .xml files encountered
            self.debug('%s does not have registry as root tag' % self.filename)
            return

        # shouldn't have <directories> elements in registry fragments
        self._parseRoot(node, disallowed=['directories'])
        root.unlink()

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
    def parseRegistry(self, file):
        """
        @param file: The file to parse, either as an open file object,
        or as the name of a file to open.
        @type  file: str or file.
        """
        self.filename = getattr(file, 'name', '<string>')
        root = self.getRoot(file)
        self._parseRoot(root.documentElement)
        root.unlink()

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

    def removeDirectoryByPath(self, path):
        """
        Remove a directory from the parser given the path.
        Used when the path does not actually contain any registry information.
        """
        if path in self._directories.keys():
            del self._directories[path]

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

        if disallowed:
            for k in disallowed:
                del parsers[k]

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
class RegistryDirectory(log.Loggable):
    """
    I represent a directory under a path managed by the registry.
    I can be queried for a list of partial registry .xml files underneath
    the given path, under the given prefix.
    """
    def __init__(self, path, prefix='flumotion'):
        self._path = path
        self._prefix = prefix
        scanPath = os.path.join(path, prefix)
        self._files, self._dirs = self._getFileLists(scanPath)

    def __repr__(self):
        return "<RegistryDirectory %s>" % self._path

    def _getFileLists(self, root):
        """
        Get all files ending in .xml from all directories under the given root.

        @type  root: string
        @param root: the root directory under which to search

        @returns: a list of .xml files, relative to the given root directory
        """
        files = []
        dirs = []

        if os.path.exists(root):
            try:
                directory_files = os.listdir(root)
            except OSError, e:
                if e.errno == errno.EACCES:
                    return files, dirs
                else:
                    raise

            dirs.append(root)

            for dir in directory_files:
                filename = os.path.join(root, dir)
                # if it's a .xml file, then add it to the list
                if not os.path.isdir(filename):
                    if filename.endswith('.xml'):
                        files.append(filename)
                # if it's a directory and not an svn directory, then get
                # its files and add them
                elif dir != '.svn':
                    newFiles, newDirs = self._getFileLists(filename)
                    files.extend(newFiles)
                    dirs.extend(newDirs)

        return files, dirs

    def rebuildNeeded(self, mtime):
        def _rebuildNeeded(file):
            try:
                if _getMTime(file) > mtime:
                    self.debug("Path %s changed since registry last "
                               "scanned", f)
                    return True
                return False
            except OSError:
                self.debug("Failed to stat file %s, need to rescan", f)
                return True

        assert self._files, "Path %s does not have registry files" % self._path
        for f in self._files:
            if _rebuildNeeded(f):
                return True
        for f in self._dirs:
            if _rebuildNeeded(f):
                return True
        return False

    def getFiles(self):
        """
        Return a list of all .xml registry files underneath this registry
        path.
        """
        return self._files

    def getPath(self):
        return self._path

class RegistryWriter(log.Loggable):
    def __init__(self, components, plugs, bundles, directories):
        """
        @param components: components to write
        @type  components: list of L{RegistryEntryComponent}
        @param plugs: plugs to write
        @type  plugs: list of L{RegistryEntryPlug}
        @param bundles: bundles to write
        @type  bundles: list of L{RegistryEntryBundle}
        @param directories: directories to write
        @type  directories: list of L{RegistryEntryDirectory}
        """
        self.components = components
        self.plugs = plugs
        self.bundles = bundles
        self.directories = directories

    def dump(self, fd):
        """
        Dump the cache of components to the given opened file descriptor.

        @type  fd: integer
        @param fd: open file descriptor to write to
        """

        def w(i, msg):
            print >> fd, ' '*i + msg
        def e(attr):
            return saxutils.quoteattr(attr)

        def _dump_proplist(i, proplist, ioff=2):
            for prop in proplist:
                if isinstance(prop, RegistryEntryCompoundProperty):
                    _dump_compound(i, prop)
                else:
                    w(i, ('<property name="%s" type="%s"'
                          % (prop.getName(), prop.getType())))
                    w(i, ('          description=%s'
                          % (e(prop.getDescription()),)))
                    w(i, ('          required="%s" multiple="%s"/>'
                          % (prop.isRequired(), prop.isMultiple())))

        def _dump_compound(i, cprop, ioff=2):
            w(i, ('<compound-property name="%s"' % (cprop.getName(),)))
            w(i, ('                   description=%s'
                  % (e(cprop.getDescription()),)))
            w(i, ('                   required="%s" multiple="%s">'
                  % (cprop.isRequired(), cprop.isMultiple())))
            _dump_proplist(i + ioff, cprop.getProperties())
            w(i, ('</compound-property>'))

        w(0, '<registry>')
        w(0, '')

        # Write components
        w(2, '<components>')
        w(0, '')
        for component in self.components:
            w(4, '<component type="%s" base="%s"' % (
                component.getType(), component.getBase()))
            w(4, '           description=%s>'
                % (e(component.getDescription()),))

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
            _dump_proplist(8, component.getProperties())
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
        for plug in self.plugs:
            w(4, '<plug type="%s" socket="%s">'
              % (plug.getType(), plug.getSocket()))

            entry = plug.getEntry()
            w(6, ('<entry location="%s" function="%s"/>'
                  % (entry.getLocation(), entry.getFunction())))

            w(6, '<properties>')
            _dump_proplist(8, plug.getProperties())
            w(6, '</properties>')

            w(4, '</plug>')
            w(0, '')

        w(2, '</plugs>')
        w(0, '')

        # bundles
        w(2, '<bundles>')
        for bundle in self.bundles:
            w(4, '<bundle name="%s" under="%s" project="%s">' % (
                bundle.getName(), bundle.getUnder(), bundle.getProject()))

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
        directories = self.directories
        if directories:
            w(2, '<directories>')
            w(0, '')
            for d in directories:
                w(4, '<directory filename="%s"/>' % d.getPath())
            w(2, '</directories>')
            w(0, '')

        w(0, '</registry>')

class ComponentRegistry(log.Loggable):
    """Registry, this is normally not instantiated."""

    logCategory = 'registry'
    filename = os.path.join(configure.registrydir, 'registry.xml')

    def __init__(self):
        self._parser = RegistryParser()

        if (READ_CACHE and
            os.path.exists(self.filename) and
            os.access(self.filename, os.R_OK)):
            self.info('Parsing registry: %s' % self.filename)
            try:
                self._parser.parseRegistry(self.filename)
            except fxml.ParserError, e:
                # this can happen for example if we upgraded to a new version,
                # ran, then downgraded again; the registry can then contain
                # XML keys that are not understood by this version.
                # This is non-fatal, and gets fixed due to a re-scan
                self.warning('Could not parse registry %s.' % self.filename)
                self.debug('fxml.ParserError: %s' % log.getExceptionMessage(e))

        self.verify(force=not READ_CACHE)

    def addFile(self, file):
        """
        @param file: The file to add, either as an open file object, or
        as the name of a file to open.
        @type  file: str or file.
        """
        if isinstance(file, str) and file.endswith('registry.xml'):
            self.warning('%s seems to be an old registry in your tree, '
                         'please remove it', file)
        self.debug('Adding file: %r', file)
        self._parser.parseRegistryFile(file)

    def addFromString(self, string):
        f = StringIO(string)
        self.addFile(f)
        f.close()

    def addRegistryPath(self, path, prefix='flumotion'):
        """
        Add a registry path to this registry, scanning it for registry
        snippets.

        @param path: a full path containing a 'flumotion' directory,
                     which will be scanned for registry files.

        @rtype:   bool
        @returns: whether the path could be added
        """
        self.debug('path %s, prefix %s' % (path, prefix))
        if not os.path.exists(path):
            self.warning("Cannot add non-existent path '%s' to registry" % path)
            return False
        if not os.path.exists(os.path.join(path, prefix)):
            self.warning("Cannot add path '%s' to registry "
                "since it does not contain prefix '%s'" % (path, prefix))
            return False

        # registry path was either not watched or updated, or a force was
        # asked, so reparse
        self.info('Scanning registry path %s' % path)
        registryPath = RegistryDirectory(path, prefix=prefix)
        files = registryPath.getFiles()
        self.debug('Found %d possible registry files' % len(files))
        map(self.addFile, files)

        self._parser.addDirectory(registryPath)
        return True

    # fixme: these methods inconsistenly molest and duplicate those of
    # the parser.
    def isEmpty(self):
        return len(self._parser._components) == 0

    def getComponent(self, name):
        """
        @rtype: L{RegistryEntryComponent}
        """
        return self._parser.getComponent(name)

    def hasComponent(self, name):
        return name in self._parser._components

    def getComponents(self):
        return self._parser.getComponents()

    def getPlug(self, type):
        """
        @rtype: L{RegistryEntryPlug}
        """
        return self._parser.getPlug(type)

    def hasPlug(self, name):
        return name in self._parser._plugs

    def getPlugs(self):
        return self._parser.getPlugs()

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
        writer = RegistryWriter(self.getComponents(), self.getPlugs(),
                                self.getBundles(), self.getDirectories())
        writer.dump(fd)

    def clean(self):
        """
        Clean the cache of components.
        """
        self._parser.clean()

    def rebuildNeeded(self):
        if not os.path.exists(self.filename):
            return True

        # A bit complicated because we want to allow FLU_PROJECT_PATH to
        # point to nonexistent directories
        registryPaths = sets.Set(self._getRegistryPathsFromEnviron())
        oldRegistryPaths = sets.Set([dir.getPath()
                                     for dir in self.getDirectories()])
        if registryPaths != oldRegistryPaths:
            if oldRegistryPaths - registryPaths:
                return True
            if filter(os.path.exists, registryPaths - oldRegistryPaths):
                return True

        registry_modified = _getMTime(self.filename)
        for d in self._parser.getDirectories():
            if d.rebuildNeeded(registry_modified):
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

    def _getRegistryPathsFromEnviron(self):
        registryPaths = [configure.pythondir, ]
        if os.environ.has_key('FLU_PROJECT_PATH'):
            paths = os.environ['FLU_PROJECT_PATH']
            registryPaths += paths.split(':')
        return registryPaths

    def verify(self, force=False):
        """
        Verify if the registry is uptodate and rebuild if it is not.

        @param force: True if the registry needs rebuilding for sure.
        """
        # construct a list of all paths to scan for registry .xml files
        if force or self.rebuildNeeded():
            self.info("Rebuilding registry")
            self.clean()
            for path in self._getRegistryPathsFromEnviron():
                if not self.addRegistryPath(path):
                    self._parser.removeDirectoryByPath(path)
            self.save(True)

class RegistrySubsetWriter(RegistryWriter):
    def __init__(self, fromRegistry=None, onlyBundles=None):
        """
        @param fromRegistry: The registry to subset, or the default.
        @type  fromRegistry: L{ComponentRegistry}
        @param onlyBundles: If given, only include the subset of the
        registry that is provided by bundles whose names are in this
        list.
        @type  onlyBundles: list of str
        """
        self.fromRegistry = fromRegistry
        self.onlyBundles = onlyBundles

    def dump(self, fd):
        reg = self.fromRegistry or getRegistry()
        pred = None
        if self.onlyBundles is not None:
            pred = lambda b: b.name in self.onlyBundles
        bundles = filter(pred, reg.getBundles())

        bundledfiles = {}
        for b in bundles:
            for d in b.getDirectories():
                for f in d.getFiles():
                    filename = os.path.join(d.getName(), f.getLocation())
                    bundledfiles[filename] = b

        def fileIsBundled(basedir, filename):
            return os.path.join(basedir, filename) in bundledfiles

        pred = lambda c: (filter(lambda f: fileIsBundled(c.getBase(),
                                                         f.getFilename()),
                                 c.getFiles())
                          or filter(lambda e: fileIsBundled(c.getBase(),
                                                            e.getLocation()),
                                    c.getEntries()))
        components = filter(pred, reg.getComponents())

        pred = lambda p: p.getEntry().getLocation() in bundledfiles
        plugs = filter(pred, reg.getPlugs())

        directories = [] # no need for this

        regwriter = RegistryWriter(components, plugs, bundles, directories)
        regwriter.dump(fd)

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
