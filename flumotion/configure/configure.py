# -*- Mode: Python; test-case-name: flumotion.test.test_configure -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/configure/configure.py: configure-time options for (un)installed
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

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

for key, value in config_dict.items():
    dictionary = locals()
    dictionary[key] = value
