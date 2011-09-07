# -*- Mode: Python; test-case-name: flumotion.test.test_common_xdg -*-
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

"""Simple XDG Base Directory Specification implementation.

See http://standards.freedesktop.org/basedir-spec/basedir-spec-0.6.html

Currently only configuration files handling is implemented."""


import os
from flumotion.common.python import makedirs


APPLICATION = 'flumotion'


def config_home_path():
    """
    Get the path of the config directory, taking into account the
    XDG_CONFIG_HOME environment variable.
    """

    # if $HOME is unset, there's not much we can do, default to the workdir
    home = os.environ.get('HOME', '')
    config_home = os.environ.get('XDG_CONFIG_HOME')
    if not config_home:
        config_home = os.path.join(home, '.config')
    return config_home


def config_read_path(name):
    """
    Get the path of the config file with the given name, taking into account
    the XDG_CONFIG_HOME and XDG_CONFIG_DIRS environment variables.

    @param name: The name of the config file
    @type  name: str

    @returns: full path to the file or None if it does not exist
    """

    search_path = [config_home_path()]

    config_dirs = os.environ.get('XDG_CONFIG_DIRS')
    if config_dirs:
        search_path.extend(config_dirs.split(':'))

    for path in search_path:
        candidate = os.path.join(path, APPLICATION, name)
        if os.access(candidate, os.F_OK | os.R_OK):
            return candidate
    return None


def config_write_path(name, mode='w'):
    """
    Get file-like object for the config file with the given name, taking into
    account the XDG_CONFIG_HOME environment variable.
    Create intermidient directories and the file itself according to the XDG
    Specification in case the file does not exist.

    May raise EnvironmentError if the file or directories cannot be created.

    @param name: The name of the config file
    @type  name: str
    @param mode: The mode to use when opening the file, 'w' by default.
    @type  mode: str

    @returns: a file-like object
    """

    path = os.path.join(config_home_path(), APPLICATION, name)
    dirname = os.path.dirname(path)

    if not os.path.exists(dirname):
        # XDG spec demands mode 0700
        makedirs(dirname, 0700)

    return file(path, mode)
