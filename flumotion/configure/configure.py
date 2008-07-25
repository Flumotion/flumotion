# -*- Mode: Python; test-case-name: flumotion.test.test_configure -*-
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

'''
configure-time variables for installed or uninstalled operation

Code should run
    >>> from flumotion.configure import configure

and then access the variables from the configure module.  For example:
    >>> print configure.gladedir

The values are decided at ./configure time.  They can be overridden at startup
by programs based on environment or options.  This allows running with
different configdir, logdir and rundir.

@var  isinstalled: whether an installed version is being run
@type isinstalled: boolean

@var  cachedir:      directory where cached code is stored
@type cachedir:      stringed
@var  configdir:     directory where configuration files are stored
@type configdir:     string
@var  daemondir:     directory where daemonized programs should run
@type daemondir:     string
@var  datadir:       directory where data files are stored
@type datadir:       string
@var  gladedir:      directory where glade files are stored
@type gladedir:      string
@var  logdir:        directory where log files are stored
@type logdir:        string
@var  imagedir:      directory where image files are stored
@type imagedir:      string
@var  pythondir:     directory where the flumotion python files are stored
@type pythondir:     string
@var  registrydir:   directory where the registry files are stored
@type registrydir:   string
@var  rundir:        directory where the run/pid files are stored
@type rundir:        string
@var  bindir:        directory where the flumotion executables live
@type bindir:        string
@var  sbindir:       directory where the flumotion service program lives
@type sbindir:       string

@var  defaultTCPManagerPort:  the default manager port for TCP communication
@type defaultTCPManagerPort:  int
@var  defaultSSLManagerPort:  the default manager port for SSL communication
@type defaultSSLManagerPort:  int
@var  defaultHTTPStreamPort:  the default external http streaming port
@type defaultHTTPStreamPort:  int
@var  defaultGstPortRange:    the default range of internal GStreamer ports
@type defaultGstPortRange:    list of ints

@var  PACKAGE:      Flumotion package
@type PACKAGE:      string
@var  version:      Flumotion version number
@type version:      string
@var  versionTuple: Flumotion version number
@type versionTuple: 4-tuple of integers
@var  branchName:   Flumotion branch name
@type branchName:   string

# default values for service-related stuff

@var  processTermWait: how long to wait before timing out term signals
@type processTermWait int
@var  processKillWait: how long to wait before timing out kill signals
@type processKillWait int
@var  heartbeatInterval: component heartbeat interval, in seconds
@type heartbeatInterval: int
'''

# Note: This module is loaded very early on, so
#       don't add any extra flumotion imports unless you
#       really know what you're doing

import os

__version__ = "$Rev$"

# where am I on the disk ?
__thisdir = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(__thisdir, 'uninstalled.py')):
    from flumotion.configure import uninstalled
    _config = uninstalled.get()
else:
    from flumotion.configure import installed
    _config = installed.get()

def _versionStringToTuple(versionString):
    t = tuple(map(int, versionString.split('.')))
    if len(t) < 4:
        t = t + (0,)
    return t

isinstalled = _config['isinstalled']

cachedir = _config['cachedir']
configdir = _config['configdir']
daemondir = _config['daemondir']
datadir = _config['datadir']
gladedir = _config['gladedir']
imagedir = _config['imagedir']
logdir = _config['logdir']
localedatadir = _config['localedatadir']
pythondir = _config['pythondir']
registrydir = _config['registrydir']
rundir = _config['rundir']
bindir = _config['bindir']
sbindir = _config['sbindir']

defaultTCPManagerPort = 8642
defaultSSLManagerPort = 7531
defaultHTTPStreamPort = 8800
defaultGstPortRange = range(8600, 8639 + 1)

PACKAGE = 'flumotion'
version = _config['version']
versionTuple = _versionStringToTuple(version)
branchName = 'trunk'

processTermWait = 10
processKillWait = 5
heartbeatInterval = 5



