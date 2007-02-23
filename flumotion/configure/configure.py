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
@type cachedir:      string
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
@var  defaultStreamPortRange: the default range of external streaming ports
@type defaultStreamPortRange: list of ints
@var  defaultGstPortRange:    the default range of internal GStreamer ports
@type defaultGstPortRange:    list of ints

@var  version:      Flumotion version number
@type version:      string
@var  versionTuple: Flumotion version number
@type versionTuple: 4-tuple of integers
'''

# Note: This module is loaded very early on, so
#       don't add any extra flumotion imports unless you
#       really know what you're doing

# FIXME: document all the module variables

import os

# where am I on the disk ?
__thisdir = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(__thisdir, 'uninstalled.py')):
    from flumotion.configure import uninstalled
    _config = uninstalled.get()
else:
    from flumotion.configure import installed
    _config = installed.get()

# default values for ports
_config['defaultTCPManagerPort'] = 8642
_config['defaultSSLManagerPort'] = 7531
_config['defaultStreamPortRange'] = range(8800, 8844 + 1)
_config['defaultGstPortRange'] = range(8600, 8639 + 1)

# default values for service-related stuff
# how long to wait before timing out term and kill signals
_config['processTermWait'] = 5
_config['processKillWait'] = 5

# default value for component heartbeat interval, in seconds
_config['heartbeatInterval'] = 5

def _versionStringToTuple(versionString):
    t = tuple(map(int, versionString.split('.')))
    if len (t) < 4:
        t = t + (0,)
    return t
_config['versionTuple'] = _versionStringToTuple(_config['version'])

for key, value in _config.items():
    dictionary = locals()
    dictionary[key] = value
