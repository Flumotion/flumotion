# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
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

import sys

from flumotion.twisted import errors

# environment variables controlling levels for each category
global FLU_DEBUG

_log_handlers = []

def stderrHandler(category, type, message):
    sys.stderr.write('[%s:%s] %s\n' % (category, type, message))
    sys.stderr.flush()

def stderrHandlerLimited(category, type, message):
    'used when FLU_DEBUG is set; uses FLU_DEBUG to limit on category'
    # FIXME: we should parse FLU_DEBUG into a hash so we can look up
    # if the given category matches  
    sys.stderr.write('[%s:%s] %s\n' % (category, type, message))
    sys.stderr.flush()

def log(category, type, message):
    global _log_handlers

    for handler in _log_handlers:
        handler(category, type, message)
    
def debug(cat, *args):
    log(cat, 'DEBUG', ' '.join(args))

def msg(cat, *args):
    log(cat, 'INFO', ' '.join(args))

def warn(cat, *args):
    log(cat, 'WARNING', ' '.join(args))

def error(cat, *args):
    msg = ' '.join(args)
    log(cat, 'ERROR', msg)
    raise errors.SystemError(msg)

def enableLogging():
    global _log_handlers
    if not stderrHandler in _log_handlers:
        _log_handlers.append(stderrHandler)
    
def disableLogging():
    if stderrHandler in _log_handlers:
        _log_handlers.remove(stderrHandler)
    
    _do_logging = False
    
def addLogHandler(func):
    _log_handlers.append(func)

import os
if os.environ.has_key('FLU_DEBUG'):
    # install a log handler that uses the value of FLU_DEBUG
    FLU_DEBUG = os.environ['FLU_DEBUG']
    addLogHandler(stderrHandlerLimited)
    debug('log', "FLU_DEBUG set to %s" % FLU_DEBUG)
