# -*- Mode: Python; test-case-name: flumotion.test.test_configure -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/configure/configure.py: configure-time options for (un)installed
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

'''
Exports configure-time variables for installed or uninstalled operation.

Code should run
    >>> from flumotion.configure import configure

and then access the variables from the configure module.  For example:
    >>> print configure.gladedir

@var  isinstalled: whether an installed version is being run
@type isinstalled: boolean

@var  configdir:     directory where configuration files are stored
@type configdir:     string
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

@var  defaultTCPManagerPort:  the default manager port for TCP communication
@type defaultTCPManagerPort:  int
@var  defaultSSLManagerPort:  the default manager port for SSL communication
@type defaultSSLManagerPort:  int
@var  defaultStreamPortRange: the default range of external streaming ports
@type defaultStreamPortRange: list of ints
@var  defaultGstPortRange:    the default range of internal GStreamer ports
@type defaultGstPortRange:    list of ints

@var  version:     Flumotion version number
@type version:     string
'''

# FIXME: document all the module variables

import os
import flumotion.configure

# where am I on the disk ?
__thisdir = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(__thisdir, 'uninstalled.py')):
    from flumotion.configure import uninstalled
    config_dict = uninstalled.get()
else:
    from flumotion.configure import installed
    config_dict = installed.get()

# default values for ports
config_dict['defaultTCPManagerPort'] = 8642
config_dict['defaultSSLManagerPort'] = 7531
config_dict['defaultStreamPortRange'] = range(8800, 8844 + 1)
config_dict['defaultGstPortRange'] = range(8600, 8639 + 1)

for key, value in config_dict.items():
    dictionary = locals()
    dictionary[key] = value
