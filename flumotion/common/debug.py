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
Debugging helper code
"""


import sys
import re
from twisted.python.reflect import filenameToModuleName


_tracing = 0
_indent = ''

def trace_start(func_filter=None, print_returns=False):
    global _tracing, _indent
    
    if func_filter:
        func_filter = re.compile(func_filter)

    def do_trace(frame, event, arg):
        global _tracing, _indent
        
        if not _tracing:
            print '[tracing stopped]'
            return None
        elif event == 'line':
            return do_trace
        elif event == 'call' or event == 'c_call':
            code = frame.f_code
            if func_filter and not func_filter.match(code.co_name):
                return None
            if code.co_name == '?':
                return None
            module = filenameToModuleName(code.co_filename)
            print ('%s%s:%d:%s():'
                   % (_indent, module, code.co_firstlineno, code.co_name))
            _indent += '  '
            return do_trace
        elif event == 'return' or event == 'c_return':
            if print_returns:
                print '%sreturn %r' % (_indent, arg)
            _indent = _indent[:-2]
            return None
        elif event == 'exception' or event == 'c_exception':
            print '%sException: %r' % (_indent, arg)
            return do_trace
        else:
            print 'unknown event: %s' % event
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
