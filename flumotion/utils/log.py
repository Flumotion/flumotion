# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# flumotion/utils/log.py: logging for Flumotion server
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

"""
This module provides logging to Flumotion components.

Just like in GStreamer, five levels are defined.
These are, in order of decreasing verbosity: log, debug, info, warning, error.

API Stability: unstable

Maintainer: U{Thomas Vander Stichele <thomas at apestaart dot org>}
"""

import sys
import os
import fnmatch

from flumotion.twisted import errors

class Loggable:
    """
    Base class for objects that want to be able to log messages with
    different level of severity.  The levels are, in order from least
    to most: log, debug, info, warning, error.

    @cvar logCategory: Implementors can provide a category to log their
       messages under.
    """

    logCategory = 'default'
    
    def error(self, *args):
        "Log an error.  By default this will also raise an exception."""
        error(self.logCategory, self.logFunction(*args))
        
    def warning(self, *args):
        "Log a warning.  Used for non-fatal problems."
        warning(self.logCategory, self.logFunction(*args))
        
    def info(self, *args):
        "Log an informational message.  Used for normal operation."
        info(self.logCategory, self.logFunction(*args))

    def debug(self, *args):
        "Log a debug message.  Used for debugging."
        debug(self.logCategory, self.logFunction(*args))

    def log(self, *args):
        "Log a log message.  Used for debugging recurring events."
        log(self.logCategory, self.logFunction(*args))

    def logFunction(self, message):
        "Overridable log function.  Default just returns passed message."
        return message

# environment variables controlling levels for each category
_FLU_DEBUG="*:1"

# dynamic dictionary of categories already seen and their level
_categories = {}

# log handlers registered
_log_handlers = []

# level -> number dict
_levels = {
    "ERROR": 1,
    "WARNING": 2,
    "INFO": 3,
    "DEBUG": 4,
    "LOG": 5
}

def registerCategory(category):
    """
    Register a given category in the debug system.
    A level will be assigned to it based on the setting of FLU_DEBUG.
    """
    # parse what level it is set to based on FLU_DEBUG
    # example: *:2,admin:4
    global _FLU_DEBUG
    global _levels
    global _categories

    level = 0
    chunks = _FLU_DEBUG.split(',')
    for chunk in chunks:
        if not chunk:
            continue
        (spec, value) = chunk.split(':')
        # our glob is unix filename style globbing, so cheat with fnmatch
        # fnmatch.fnmatch didn't work for this, so don't use it
        if category in fnmatch.filter((category, ), spec):
            # we have a match, so set level based on string or int
            if not value:
                continue
            if _levels.has_key(value):
                level = _levels[value]
            else:
                level = int(value)
    # store it
    _categories[category] = level

def stderrHandler(category, level, message):
    sys.stderr.write('%-8s %-15s %s\n' % (level + ':', category + ':' , message))
    sys.stderr.flush()

def stderrHandlerLimited(category, level, message):
    """
    Logs the message only when the message's level is not more verbose
    than the registered level for this category.
    """
    
    'used when FLU_DEBUG is set; uses FLU_DEBUG to limit on category'
    global _categories
    if not _categories.has_key(category):
        registerCategory(category)
    global _levels
    if _levels[level] > _categories[category]:
        return
    sys.stderr.write('%-8s %-15s %s\n' % (level + ':', category + ':' , message))
    sys.stderr.flush()

def _handle(category, level, message):
    global _log_handlers

    for handler in _log_handlers:
        handler(category, level, message)
    
def error(cat, *args):
    """
    Log a fatal error message in the given category. \
    This will also raise a L{flumotion.twisted.errors.SystemError}.
    """
    msg = ' '.join(args)
    _handle(cat, 'ERROR', msg)
    raise errors.SystemError(msg)

def warning(cat, *args):
    _handle(cat, 'WARNING', ' '.join(args))

def info(cat, *args):
    _handle(cat, 'INFO', ' '.join(args))

def debug(cat, *args):
    _handle(cat, 'DEBUG', ' '.join(args))

def log(cat, *args):
    _handle(cat, 'LOG', ' '.join(args))

def enableLogging():
    global _log_handlers
    if not stderrHandler in _log_handlers:
        _log_handlers.append(stderrHandler)
    
def disableLogging():
    if stderrHandler in _log_handlers:
        _log_handlers.remove(stderrHandler)
    
def addLogHandler(func):
    _log_handlers.append(func)

def init():
    if os.environ.has_key('FLU_DEBUG'):
        # install a log handler that uses the value of FLU_DEBUG
        global _FLU_DEBUG
        _FLU_DEBUG = os.environ['FLU_DEBUG']
        addLogHandler(stderrHandlerLimited)
        debug('log', "FLU_DEBUG set to %s" % _FLU_DEBUG)
