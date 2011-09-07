# -*- Mode: Python -*-
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

"""getting coherent errors when calling procedures in named modules
"""

from twisted.python import reflect

from flumotion.common import errors, log

__version__ = "$Rev$"


def reflectCall(moduleName, methodName, *args, **kwargs):
    """
    @param moduleName: name of the module to load
    @type  moduleName: string
    @param methodName: name of the function to call
    @type  methodName: string

    Invokes a function in a given module.
    """

    log.debug('reflectcall', 'Loading moduleName %s', moduleName)

    module = reflect.namedModule(moduleName)

    log.debug('reflectcall', 'calling method %s.%s', moduleName,
              methodName)

    proc = getattr(module, methodName)
    return proc(*args, **kwargs)


def reflectCallCatching(err, moduleName, methodName, *args, **kwargs):
    """
    @param err: The type of error to throw
    @type err: Exception
    @param moduleName: name of the module to load
    @type  moduleName: string
    @param methodName: name of the function to call
    @type  methodName: string

    Invokes a function in a given module, marshalling all errors to be
    of a certain type.
    """

    log.debug('reflectcall', 'Loading moduleName %s' % moduleName)

    try:
        module = reflect.namedModule(moduleName)
    except ValueError:
        raise err("module %s could not be found" % moduleName)
    except SyntaxError, e:
        raise err("module %s has a syntax error in %s:%d"
                  % (moduleName, e.filename, e.lineno))
    except ImportError, e:
        # FIXME: basically this is the same as the generic one below...
        raise err("module %s could not be imported (%s)"
                  % (moduleName,
                     log.getExceptionMessage(e, filename='flumotion')))
    except Exception, e:
        raise err("module %s could not be imported (%s)"
                  % (moduleName,
                     log.getExceptionMessage(e, filename='flumotion')))

    if not hasattr(module, methodName):
        raise err("module %s has no method named %s"
                  % (moduleName, methodName))

    log.debug('reflectcall', 'calling method %s.%s'
              % (moduleName, methodName))

    try:
        ret = getattr(module, methodName)(*args, **kwargs)
    except err:
        # already nicely formatted, so fall through
        log.debug('reflectcall', 'letting error fall through')
        raise
    except Exception, e:
        msg = log.getExceptionMessage(e)
        log.warning('reflectcall', msg)
        log.warning('reflectcall', 'raising error')
        raise err(msg)

    log.debug('reflectcall', 'returning %r' % ret)

    return ret


def createComponent(moduleName, methodName, config):
    """
    @param moduleName: name of the module to create the component from
    @type  moduleName: string
    @param methodName: the factory method to use to create the component
    @type  methodName: string
    @param config: the component's config dict
    @type  config: dict

    Invokes the entry point for a component in the given module using the
    given factory method, thus creating the component.

    @rtype: L{flumotion.component.component.BaseComponent}
    """
    return reflectCallCatching(errors.ComponentCreateError,
                               moduleName, methodName, config)
