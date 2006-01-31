# -*- Mode: Python; test-case-name: flumotion.test.test_log -*-
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
import traceback

# environment variables controlling levels for each category
_FLU_DEBUG = "*:1"

# dynamic dictionary of categories already seen and their level
_categories = {}

# log handlers registered
_log_handlers = []
_log_handlers_limited = []

_initialized = False

# public log levels
ERROR = 1
WARN = 2
INFO = 3
DEBUG = 4
LOG = 5

def getLevelName(level):
    """
    Return the name of a log level.
    """
    assert isinstance(level, int) and level > 0 and level < 6, \
           "Bad debug level"
    return ('ERROR', 'WARN', 'INFO', 'DEBUG', 'LOG')[level - 1]

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
            try:
                level = int(value)
            except ValueError: # e.g. *; we default to most
                level = 5
    # store it
    _categories[category] = level

def getCategoryLevel(category):
    """
    @param category: string

    Get the debug level at which this category is being logged, adding it
    if it wasn't registered yet.
    """
    global _categories
    if not _categories.has_key(category):
        registerCategory(category)
    return _categories[category]

def _canShortcutLogging(category, level):
    if _log_handlers:
        # we have some loggers operating without filters, have to do
        # everything
        return False
    else:
        return level > getCategoryLevel(category)

def scrubFilename(filename):
    '''
    Scrub the filename of everything before 'flumotion' and'twisted' to make them shorter.
    '''
    i = filename.rfind('flumotion')
    if i != -1:
        #filename = filename[i + len('flumotion') + 1:]
        filename = filename[i:]
    else:
        # only pure twisted, not flumotion.twisted
        i = filename.rfind('twisted')
        if i != -1:
            filename = filename[i:]
    
    return filename

def _handle(level, object, category, message):
    def getFileLine():
        # Return a tuple of (file, line) for the first stack entry
        # outside of log.py (which would be the caller of log)
        frame = sys._getframe()
        while frame:
            co = frame.f_code
            if not co.co_filename.endswith('log.py'):
                return scrubFilename(co.co_filename), frame.f_lineno
            frame = frame.f_back
            
        return "Not found", 0

    # first all the unlimited ones
    if _log_handlers:
        (file, line) = getFileLine()
        for handler in _log_handlers:
            try:
                handler(level, object, category, file, line, message)
            except TypeError:
                raise SystemError, "handler %r raised a TypeError" % handler

    if level > getCategoryLevel(category):
        return

    # set this a second time, just in case there weren't unlimited
    # loggers there before
    (file, line) = getFileLine()

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
    _handle(ERROR, object, cat, ' '.join(args))

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
    _handle(WARN, object, cat, ' '.join(args))

def infoObject(object, cat, *args):
    """
    Log an informational message in the given category.
    """
    _handle(INFO, object, cat, ' '.join(args))

def debugObject(object, cat, *args):
    """
    Log a debug message in the given category.
    """
    _handle(DEBUG, object, cat, ' '.join(args))

def logObject(object, cat, *args):
    """
    Log a log message.  Used for debugging recurring events.
    """
    _handle(LOG, object, cat, ' '.join(args))

error = lambda cat, *args: errorObject(None, cat, *args)
warning = lambda cat, *args: warningObject(None, cat, *args)
info = lambda cat, *args: infoObject(None, cat, *args)
debug = lambda cat, *args: debugObject(None, cat, *args)
log = lambda cat, *args: logObject(None, cat, *args)

#warningFailure = lambda failure: Loggable.warningFailure(None, '', failure)
warningFailure = lambda failure: warning('', getFailureMessage(failure))

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
        if _canShortcutLogging(self.logCategory, ERROR):
            return
        errorObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))
        
    def warning(self, *args):
        """Log a warning.  Used for non-fatal problems."""
        if _canShortcutLogging(self.logCategory, WARN):
            return
        warningObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))
        
    def info(self, *args):
        """Log an informational message.  Used for normal operation."""
        if _canShortcutLogging(self.logCategory, INFO):
            return
        infoObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))

    def debug(self, *args):
        """Log a debug message.  Used for debugging."""
        if _canShortcutLogging(self.logCategory, DEBUG):
            return
        debugObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))

    def log(self, *args):
        """Log a log message.  Used for debugging recurring events."""
        if _canShortcutLogging(self.logCategory, LOG):
            return
        logObject(self.logObjectName(), self.logCategory,
            self.logFunction(*args))

    def warningFailure(self, failure):
        """
        Log a warning about a Failure. Useful as an errback handler:
        d.addErrback(self.warningFailure)
        """
        if _canShortcutLogging(self.logCategory, WARN):
            return
        warningObject(self.logObjectName(), self.logCategory,
            self.logFunction(getFailureMessage(failure)))

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

# we need an object as the observer because startLoggingWithObserver
# expects a bound method
class FluLogObserver(Loggable):
    """
    Twisted log observer that integrates with Flumotion's logging.
    """
    logCategory = "logobserver"

    def __init__(self):
        self._ignoreErrors = []

    def emit(self, eventDict):
        method = log # by default, lowest level
        edm = eventDict['message']
        if not edm:
            if eventDict['isError'] and eventDict.has_key('failure'):
                f = eventDict['failure']
                for type in self._ignoreErrors:
                    r = f.check(type)
                    if r:
                        self.debug("Failure of type %r, ignoring" % type)
                        return
                    
                self.log("Failure %r" % f)

                method = debug # tracebacks from errors at debug level
                msg = "A python traceback occurred."
                if getCategoryLevel("twisted") < WARN:
                    msg += "  Run with debug level >= 2 to see the traceback."
                # and an additional warning
                warning('twisted', msg)
                text = f.getTraceback()
                print "\nTwisted traceback:\n"
                print text
            elif eventDict.has_key('format'):
                text = eventDict['format'] % eventDict
            else:
                # we don't know how to log this
                return
        else:
            text = ' '.join(map(str, edm))

        fmtDict = { 'system': eventDict['system'],
                    'text': text.replace("\n", "\n\t")
                  }
        msgStr = " [%(system)s] %(text)s\n" % fmtDict
        method('twisted', msgStr)

    def ignoreErrors(self, *types):
        for type in types:
            self._ignoreErrors.append(type)

    def clearIgnores(self):
        self._ignoreErrors = []

# make a singleton
__theFluLogObserver = None

def getTheFluLogObserver():
    global __theFluLogObserver

    if not __theFluLogObserver:
        __theFluLogObserver = FluLogObserver()

    return __theFluLogObserver

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
            getLevelName(level), os.getpid(), o, category,
            time.strftime("%b %d %H:%M:%S")))
        sys.stderr.write('%-4s %s %s\n' % ("", message, where))

        # old: 5 + 1 + 20 + 1 + 12 + 1 + 32 + 1 + 7 == 80
        #sys.stderr.write('%-5s %-20s %-12s %-32s [%5d] %-4s %-15s %s\n' % (
        #    level, o, category, where, os.getpid(),
        #    "", time.strftime("%b %d %H:%M:%S"), message))
        sys.stderr.flush()
    except IOError:
        # happens in SIGCHLDHandler for example
        pass

def addLogHandler(func, limited=True):
    """
    Add a custom log handler.

    @param func:    a function object
                    with prototype (level, object, category, message)
                    where level is either ERROR, WARN, INFO, DEBUG, or
                    LOG, and the rest of the arguments are strings or
                    None. Use getLevelName(level) to get a printable
                    name for the log level.
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
    global _initialized

    if _initialized:
        return

    if os.environ.has_key('FLU_DEBUG'):
        # install a log handler that uses the value of FLU_DEBUG
        setFluDebug(os.environ['FLU_DEBUG'])
    addLogHandler(stderrHandler, limited=True)

    _initialized = True

_initializedTwisted = False

def logTwisted():
    """
    Integrate twisted's logger with Flumotion's logger.

    This is done in a separate method because calling this imports and sets
    up a reactor.  Since we want basic logging working before choosing a
    reactor, we need to separate these.
    """
    global _initializedTwisted

    if _initializedTwisted:
        return

    log.debug('log', 'Integrating twisted logger')

    # integrate twisted's logging with us
    from twisted.python import log as tlog

    # this call imports the reactor
    # that is why we do this in a separate method
    from twisted.spread import pb

    # we don't want logs for pb.Error types since they
    # are specifically raised to be handled on the other side
    observer = getTheFluLogObserver()
    observer.ignoreErrors([pb.Error,])
    tlog.startLoggingWithObserver(observer.emit, False)

    _initializedTwisted = True

def reset():
    """
    Resets the logging system, removing all log handlers.
    """
    global _log_handlers, _log_handlers_limited, _initialized
    
    _log_handlers = []
    _log_handlers_limited = []
    _initialized = False
    
def setFluDebug(string):
    """Set the FLU_DEBUG string.  This controls the log output."""
    global _FLU_DEBUG
    global _categories
    
    _FLU_DEBUG = string
    debug('log', "FLU_DEBUG set to %s" % _FLU_DEBUG)

    # reparse all already registered category levels
    for category in _categories:
        registerCategory(category)

def getExceptionMessage(exception):
    stack = traceback.extract_tb(sys.exc_info()[2])
    (filename, line, func, text) = stack[-1]
    filename = scrubFilename(filename)
    exc = exception.__class__.__name__
    msg = ""
    # a shortcut to extract a useful message out of most flumotion errors
    # for now
    if len(exception.args) == 1 and isinstance(exception.args[0], str):
        msg = ": %s" % exception.args[0]
    return "exception %(exc)s at %(filename)s:%(line)s: %(func)s()%(msg)s" % locals()

def getFailureMessage(failure):
    exc = str(failure.type)
    msg = failure.getErrorMessage()
    if len(failure.frames) == 0:
        return "failure %(exc)s: %(msg)s" % locals()

    (func, filename, line, some, other) = failure.frames[-1]
    filename = scrubFilename(filename)
    return "failure %(exc)s at %(filename)s:%(line)s: %(func)s(): %(msg)s" % locals()
