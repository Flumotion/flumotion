# -*- Mode: Python; test-case-name: flumotion.test.test_registry -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/common/registry.py: component registry handling
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
Parsing of registry.
"""

import os
import stat
import errno

from xml.dom import minidom, Node
from xml.parsers import expat

from twisted.python import reflect

from flumotion.common import common, log
from flumotion.configure import configure

__all__ = ['ComponentRegistry', 'registry']

def istrue(value):
    if value in ('True', 'true', '1', 'yes'):
        return True

    return False

def getMTime(file):
    return os.stat(file)[stat.ST_MTIME]

class RegistryEntryComponent:
    "This class represents a <component> entry in the registry"
    def __init__(self, filename, type, 
                 source='', properties=[], files=[]):
        self.filename = filename
        self.type = type
        self.source = source
        self.properties = properties
        self.files = files
        
    def getProperties(self):
        return self.properties

    def getFiles(self):
        return self.files

    def getGUIEntry(self):
        if not self.files:
            return
        
        # FIXME: Handle multiple files
        if len(self.files) > 1:
            return
        
        return self.files[0].getFilename()
    
    def getType(self):
        return self.type

    def getSource(self):
        return self.source
    
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
    
class XmlParserError(Exception):
    pass

class XmlDeprecatedError(Exception):
    pass


# TODO
# Bundles

class RegistryParser(log.Loggable):
    """
    Registry parser

    I have two modes, one to parse registries and another one to parse
    standalone component files.

    For parsing registries use the parseRegistry function and for components
    use parseFile.

    I also have a list of all components and directories which the
    directory use (instead of saving its own copy)
    """
    
    def __init__(self):
        self._components = {}
        self._directories = {}
        
    def clean(self):
        self._components = {}
        self._directories = {}

    def _getRoot(self, filename, string):
        if string:
            self.debug('Parsing XML string')
            return minidom.parseString(string)
        else:
            self.debug('Parsing XML file: %s' % os.path.basename(filename))
            return minidom.parse(filename)
        
    def getComponents(self):
        return self._components.values()

    def getComponent(self, name):
        return self._components[name]

    def _getChildNodes(self, node, tag=''):
        if tag and node.nodeName != tag:
            raise XmlParserError(
                'expected <%s>, but <%s> found' % (tag, node.nodeName))

        return [child for child in node.childNodes
                          if (child.nodeType != Node.TEXT_NODE and
                              child.nodeType != Node.COMMENT_NODE)]
        
    def _parseComponents(self, node):
        # <components>
        #   <component>
        # </components>
        
        components = {}
        
        for child in self._getChildNodes(node, 'components'):
            if child.nodeName == 'component':
                component = self._parseComponent(child)
                components[component.getType()] = component
            else:
                raise XmlParserError("unexpected node: %s" % child)

        return components
    
    def _parseComponent(self, node):
        # <component type="...">
        #   <source>
        #   <properties>
        # </component>
        
        if not node.hasAttribute('type'):
            raise XmlParserError, "<component> must have a type attribute"
        type = str(node.getAttribute('type'))

        properties = {}
        # Merge in options for inherit
        if node.hasAttribute('inherit'):
            base_type = str(node.getAttribute('inherit'))
            base = self.getComponent(base_type)
            for prop in base.getProperties():
                properties[prop.getName()] = prop
                
        files = []
        source = None
        for child in self._getChildNodes(node):
            if child.nodeName == 'source':
                source = self._parseSource(child)
            elif child.nodeName == 'properties':
                self._parseProperties(properties, child)
            elif child.nodeName == 'files':
                files = self._parseFiles(child)
            else:
                raise XmlParserError("unexpected node: %s" % child)

        return RegistryEntryComponent(self.filename,
                                      type, source, 
                                      properties.values(), files)

    def _parseSource(self, node):
        # <source location="..."/>
        if not node.hasAttribute('location'):
            raise XmlParserError("<source> must have a location attribute")

        return str(node.getAttribute('location'))

    def _parseProperties(self, properties, node):
        # <properties>
        #   <property name="..." type="" required="yes/no" multiple="yes/no"/>
        #  </properties>
        
        for child in self._getChildNodes(node):
            if child.nodeName != "property":
                raise XmlParserError("unexpected node: %s" % child)
        
            if not child.hasAttribute('name'):
                raise XmlParserError("<property> must have a name attribute")
            elif not child.hasAttribute('type'):
                raise XmlParserError("<property> must have a type attribute")

            name = str(child.getAttribute('name'))
            type = str(child.getAttribute('type'))

            optional = {}
            if child.hasAttribute('required'):
                optional['required'] = istrue(child.getAttribute('required'))

            if child.hasAttribute('multiple'):
                optional['multiple'] = istrue(child.getAttribute('multiple'))

            property = RegistryEntryProperty(name, type, **optional)

            properties[name] = property

    def _parseFiles(self, node):
        # <files>
        #   <file name="..." type=""/>
        #  </files>

        files = []
        for child in self._getChildNodes(node):
            if child.nodeName != "file":
                raise XmlParserError("unexpected node: %s" % child)
        
            if not child.hasAttribute('name'):
                raise XmlParserError("<file> must have a name attribute")

            if not child.hasAttribute('type'):
                raise XmlParserError("<file> must have a type attribute")

            name = str(child.getAttribute('name'))
            type = str(child.getAttribute('type'))

            dir = os.path.split(self.filename)[0]
            filename = os.path.join(dir, name)
            file = RegistryEntryFile(filename, type)
            files.append(file)
            
        return files

    ## Component registry specific functions
    def parseFile(self, filename, string=None):
        self.filename = filename

        root = self._getRoot(filename, string)
        components = self._parseComponents(root.documentElement)
        self._components.update(components)

    ## Base registry specific functions
    def parseRegistry(self, filename, string=None):
        self.filename = filename

        root = self._getRoot(filename, string)
        self._parseRoot(root.documentElement)

    def getDirectories(self):
        return self._directories.values()

    def getDirectory(self, name):
        return self._directories[name]

    def addDirectory(self, directory):
        self._directories[directory.getFilename()] = directory

    def _parseRoot(self, node):
        try:
            children = self._getChildNodes(node, 'registry')
        except XmlParserError, e:
            raise XmlDeprecatedError(e)
        
        for child in children:
            if child.nodeName == 'components':
                components = self._parseComponents(child)
                self._components.update(components)
            elif child.nodeName == 'directories':
                directories = self._parseDirectories(child)
                self._directories.update(directories)
            else:
                raise XmlParserError("unexpected node: %s" % child)
        
    def _parseDirectories(self, node):
        # <directories>
        #   <directory>
        # </directories>
        
        directories = {}
        
        for child in self._getChildNodes(node, 'directories'):
            if child.nodeName == 'directory':
                directory = self._parseDirectory(child)
                directories[directory.getFilename()] = directory
            else:
                raise XmlParserError("unexpected node: %s" % child)

        return directories

    def _parseDirectory(self, node):
        # <directory filename="..."/>
        if not node.hasAttribute('filename'):
            raise XmlParserError("<directory> must have a filename attribute")

        filename = str(node.getAttribute('filename'))
        return RegistryDirectory(filename)

    
class RegistryDirectory:
    def __init__(self, filename):
        self._filename = filename
        self._files = self._getFileList(self._filename)
        
    def _getFileList(self, root):
        """
        Get all files ending in .xml from all directories under the given root.

        @type root: string
        @param root: the root directory under which to search
        
        @returns: a list of .xml files, relative to the given root directory
        """

        files = []
        
        if os.path.exists(root):
            for dir in os.listdir(root):
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
        return max(map(getMTime, self._files))

    def getFiles(self):
        return self._files

    def getFilename(self):
        return self._filename
    
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
    
    def addFile(self, filename, string=None):
        self.debug('Adding file: %s' % filename)
        self._parser.parseFile(filename, string)
        
    def addFromString(self, string):
        self.addFile('<string>', string)
        
    def addDirectory(self, filename, force=False):
        if not os.path.exists(filename):
            return

        common.addPackagePath(filename)

        directory = self._parser._directories.get(filename, None)
        if not force:
            if directory and directory.lastModified() < getMTime(self.filename):
                return
        
        self.debug('Adding directory: %s' % filename)
        directory = RegistryDirectory(filename)
        files = directory.getFiles()
        self.debug('Found %d files' % len(files))
        map(self.addFile, files)
        
        self._parser.addDirectory(directory)
        
    def isEmpty(self):
        return len(self._parser._components) == 0

    def getComponent(self, name):
        return self._parser._components[name]

    def hasComponent(self, name):
        return self._parser._components.has_key(name)

    def getComponents(self):
        return self._parser._components.values()
    
    def getDirectories(self):
        return self._parser.getDirectories()

    def dump(self, fd):
        """
        Dump the cache of components to the given opened file descriptor.

        @type fd: integer
        @param fd: open file descriptor to write to
        """
        
        def w(i, msg):
            print >> fd, ' '*i + msg
            
        w(0, '<registry>')
        
        # Write components
        w(2, '<components>')
        for component in self.getComponents():
            w(4, '<component type="%s">' % (component.getType()))

            w(6, '<source location="%s"/>' % component.getSource())
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
                
            w(4, '</component>')
        w(2, '</components>')

        w(2, '<directories>')
        for d in self.getDirectories():
            w(4, '<directory filename="%s"/>' % d.getFilename())
        w(2, '</directories>')
        
        w(0, '</registry>')

    def clean(self):
        """
        Clean the cache of components.
        """
        self._parser.clean()

    def rebuildNeeded(self):
        if not os.path.exists(self.filename):
            return True
        
        registry_modified = getMTime(self.filename)
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
            except IOError, e:
                if e.errno == errno.EACCES:
                    self.error('Registry directory %s could not be created !' % dir)
                else:
                    raise
                
        if not os.path.isdir(dir):
            self.error('Registry directory %s is not a directory !')
        try:
            fd = open(self.filename, 'w')
            self.dump(fd)
        except IOError, e:
            if e.errno == errno.EACCES:
                self.error('Registry file %s could not be created !' % self.filename)
            else:
                raise

    def verify(self):
        path_directories = []
        path_directories.append(os.path.join(configure.pythondir,
                                             'flumotion', 'component'))
    
        if os.environ.has_key('FLU_REGISTRY_PATH'):
            paths = os.environ['FLU_REGISTRY_PATH']
            path_directories += paths.split(':')
        
        force = False
        registry_directories = [dir.getFilename()
                                  for dir in self.getDirectories()]

        # A path was removed from the environment variable
        for directory in registry_directories:
            if not directory in path_directories:
                force = True
            
        # A path was added from the environment variable
        for directory in path_directories:
            if not directory in registry_directories:
                force = True

        if force:
            self.clean()
        
        for directory in path_directories:
            self.addDirectory(directory, force)
        
        self.save(force)

registry = ComponentRegistry()

