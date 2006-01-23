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
Debugging helper code
"""


import sys
import re
import linecache

from twisted.python.reflect import filenameToModuleName


_tracing = 0
_indent = ''

def trace_start(func_filter=None, ignore_files_re=None, print_returns=False,
                write=None):
    global _tracing, _indent
    
    if func_filter:
        func_filter = re.compile(func_filter)

    if ignore_files_re:
        ignore_files_re = re.compile(ignore_files_re)

    if not write:
        def write(indent, str, *args):
            print (indent + str) % args
            
    def do_trace(frame, event, arg):
        global _tracing, _indent
        
        if not _tracing:
            print '[tracing stopped]'
            return None

        co = frame.f_code

        if event == 'line':
            return do_trace
        if func_filter and not func_filter.search(co.co_name):
            return None
        if ignore_files_re and ignore_files_re.search(co.co_filename):
            return None
        elif event == 'call' or event == 'c_call':
            if co.co_name == '?':
                return None
            module = filenameToModuleName(co.co_filename)
            write(_indent, '%s:%d:%s():', module, frame.f_lineno, co.co_name)
            _indent += '  '
            return do_trace
        elif event == 'return' or event == 'c_return':
            if print_returns:
                write(_indent, 'return %r', arg)
            _indent = _indent[:-2]
            return None
        elif event == 'exception' or event == 'c_exception':
            if arg:
                write(_indent, 'Exception: %s:%d: %s (%s)', co.co_filename,
                      frame.f_lineno, arg[0].__name__, arg[1])
            else:
                write(_indent, 'Exception: (from C)')
            return do_trace
        else:
            write(_indent, 'unknown event: %s', event)
            return None

    _tracing += 1
    if _tracing == 1:
        assert _indent == ''
        sys.settrace(do_trace)

def trace_stop():
    global _tracing, _indent
    assert _tracing > 0
    _tracing -= 1
    if not _tracing:
        sys.settrace(None)
        _indent = ''

def print_stack():
    f = sys._getframe(1)
    output = []
    while f:
        co = f.f_code
        filename = co.co_filename
        lineno = f.f_lineno
        name = co.co_name
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno)
        # reversed so we can reverse() later
        if f.f_locals:
            for k, v in f.f_locals.items():
                output.append('      %s = %r' % (k, v))
            output.append('    Locals:')
        if line:
            output.append('    %s' % line.strip())
        output.append('  File "%s", line %d, in %s' % (filename,lineno,name))
        f = f.f_back
    output.reverse()
    for line in output:
        print line

