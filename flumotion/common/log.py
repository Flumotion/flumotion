# -*- Mode: Python; test-case-name: flumotion.test.test_log -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
Flumotion logging

Just like in GStreamer, five levels of log information are defined.
These are, in order of decreasing verbosity: log, debug, info, warning, error.

API Stability: stabilizing

Maintainer: U{Thomas Vander Stichele <thomas at apestaart dot org>}
"""

import sys
import os
import fnmatch
import time

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
        """Log an error.  By default this will also raise an exception."""
        errorObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))
        
    def warning(self, *args):
        """Log a warning.  Used for non-fatal problems."""
        warningObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))
        
    def info(self, *args):
        """Log an informational message.  Used for normal operation."""
        infoObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))

    def debug(self, *args):
        """Log a debug message.  Used for debugging."""
        debugObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))

    def log(self, *args):
        """Log a log message.  Used for debugging recurring events."""
        logObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))

    def logFunction(self, message):
        """Overridable log function.  Default just returns passed message."""
        return message

    def logObjectName(self):
        """Overridable object name function."""
        # cheat pychecker
        for name in ['logName', 'name']:
            if hasattr(self, name):
                return getattr(self, name)

        return None

# environment variables controlling levels for each category
_FLU_DEBUG = "*:1"

# dynamic dictionary of categories already seen and their level
_categories = {}

# log handlers registered
_log_handlers = []
_log_handlers_limited = []

# level -> number dict
_levels = {
    "ERROR": 1,
    "WARN": 2,
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
        if ':' in chunk: 
            spec, value = chunk.split(':')
        else:
            spec = '*'
            value = chunk
            
        # our glob is unix filename style globbing, so cheat with fnmatch
        # fnmatch.fnmatch didn't work for this, so don't use it
        if category in fnmatch.filter((category, ), spec):
            # we have a match, so set level based on string or int
            if not value:
                continue
            if _levels.has_key(value):
                level = _levels[value]
            else:
                try:
                    level = int(value)
                except ValueError: # e.g. *; we default to most
                    level = 5
    # store it
    _categories[category] = level

def stderrHandler(level, object, category, file, line, message):
    """
    A log handler that writes to stdout.

    @type level:    string
    @type object:   string (or None)
    @type category: string
    @type message:  string
    """

    o = ""
    if object:
        o = '"' + object + '"'

    where = "(%s:%d)" % (file, line)

    try:
        # level   pid     object   cat      time
        # 5 + 1 + 7 + 1 + 32 + 1 + 17 + 1 + 15 == 80
        sys.stderr.write('%-5s [%5d] %-32s %-17s %-15s ' % (
            level, os.getpid(), o, category, time.strftime("%b %d %H:%M:%S")))
        sys.stderr.write('%-4s %s %s\n' % ("", message, where))

        # old: 5 + 1 + 20 + 1 + 12 + 1 + 32 + 1 + 7 == 80
        #sys.stderr.write('%-5s %-20s %-12s %-32s [%5d] %-4s %-15s %s\n' % (
        #    level, o, category, where, os.getpid(),
        #    "", time.strftime("%b %d %H:%M:%S"), message))
        sys.stderr.flush()
    except IOError:
        # happens in SIGCHLDHandler for example
        pass

def _handle(level, object, category, message):
    global _log_handlers, _log_handlers_limited

    # first all the unlimited ones
    (file, line) = getFileLine()
    for handler in _log_handlers:
        try:
            handler(level, object, category, file, line, message)
        except TypeError:
            raise SystemError, "handler %r raised a TypeError" % handler

    # the limited ones
    global _categories
    if not _categories.has_key(category):
        registerCategory(category)

    global _levels
    if _levels[level] > _categories[category]:
        return
    for handler in _log_handlers_limited:
        try:
            handler(level, object, category, file, line, message)
        except TypeError:
            raise SystemError, "handler %r raised a TypeError" % handler
    
def errorObject(object, cat, *args):
    """
    Log a fatal error message in the given category. \
    This will also raise a L{flumotion.common.errors.SystemError}.
    """
    _handle('ERROR', object, cat, ' '.join(args))

    # we do the import here because having it globally causes weird import
    # errors if our gstreactor also imports .log, which brings in errors
    # and pb stuff
    from flumotion.common.errors import SystemError
    raise SystemError(' '.join(args))

def warningObject(object, cat, *args):
    """
    Log a warning message in the given category.
    This is used for non-fatal problems.
    """
    _handle('WARN', object, cat, ' '.join(args))

def infoObject(object, cat, *args):
    """
    Log an informational message in the given category.
    """
    _handle('INFO', object, cat, ' '.join(args))

def debugObject(object, cat, *args):
    """
    Log a debug message in the given category.
    """
    _handle('DEBUG', object, cat, ' '.join(args))

def logObject(object, cat, *args):
    """
    Log a log message.  Used for debugging recurring events.
    """
    _handle('LOG', object, cat, ' '.join(args))

error = lambda cat, *args: errorObject(None, cat, *args)
warning = lambda cat, *args: warningObject(None, cat, *args)
info = lambda cat, *args: infoObject(None, cat, *args)
debug = lambda cat, *args: debugObject(None, cat, *args)
log = lambda cat, *args: logObject(None, cat, *args)

def addLogHandler(func, limited=True):
    """
    Add a custom log handler.

    @param func:    a function object
                    with prototype (level, object, category, message)
                    where all of them are strings or None.
    @type func:     a callable function
    @type limited:  boolean
    @param limited: whether to automatically filter based on FLU_DEBUG
    """

    if not callable(func):
        raise TypeError, "func must be callable"
    
    if limited:
        _log_handlers_limited.append(func)
    else:
        _log_handlers.append(func)

def init():
    """
    Initialize the logging system and parse the FLU_DEBUG environment variable.
    Needs to be called before starting the actual application.
    """
    if os.environ.has_key('FLU_DEBUG'):
        # install a log handler that uses the value of FLU_DEBUG
        setFluDebug(os.environ['FLU_DEBUG'])
    addLogHandler(stderrHandler, limited=True)

def reset():
    """
    Resets the logging system, removing all log handlers.
    """
    global _log_handlers, _log_handlers_limited
    
    _log_handlers = []
    _log_handlers_limited = []
    
def setFluDebug(string):
    """Set the FLU_DEBUG string.  This controls the log output."""
    global _FLU_DEBUG
    global _categories
    
    _FLU_DEBUG = string
    debug('log', "FLU_DEBUG set to %s" % _FLU_DEBUG)

    # reparse all already registered category levels
    for category in _categories:
        registerCategory(category)

def getFileLine():
    """
    Return a tuple of (file, line) for the first stack entry outside of
    log.py
    """
    import traceback
    stack = traceback.extract_stack()
    while stack:
        entry = stack.pop()
        if not entry[0].endswith('log.py'):
            file = entry[0]
            # strip everything before first occurence of flumotion/, inclusive
            i = file.rfind('flumotion')
            if i != -1:
                file = file[i + len('flumotion') + 1:]
            return file, entry[1]
        
    return "Not found", 0
