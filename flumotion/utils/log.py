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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import sys

_log_handlers = []

def stderrHandler(category, type, message):
    sys.stderr.write('[%s] %s %s\n' % (category, type, message))
    sys.stderr.flush()

def log(category, type, message):
    global _log_handlers

    for handler in _log_handlers:
        handler(category, type, message)
    
def msg(cat, *args):
    log(cat, 'INFO', ' '.join(args))

def warn(cat, *args):
    log(cat, 'WARNING', ' '.join(args))

def error(cat, *args):
    log(cat, 'ERROR', ' '.join(args))
    raise SystemExit

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

