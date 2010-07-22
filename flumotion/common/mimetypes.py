# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""convert mimetypes or launch an application based on one"""

__version__ = "$Rev$"
_ASSOCSTR_COMMAND = 1
_ASSOCSTR_EXECUTABLE = 2
_EXTENSIONS = {
    'application/ogg': 'ogg',
    'audio/mpeg': 'mp3',
    'audio/x-flac': 'flac',
    'audio/x-wav': 'wav',
    'multipart/x-mixed-replace': 'multipart',
    'video/mpegts': 'ts',
    'video/x-dv': 'dv',
    'video/x-flv': 'flv',
    'video/x-matroska': 'mkv',
    'video/x-ms-asf': 'asf',
    'video/x-msvideo': 'avi',
    'video/webm': 'webm',
}


def mimeTypeToExtention(mimeType):
    """Converts a mime type to a file extension.
    @param mimeType: the mime type
    @returns: file extenion if found or data otherwise
    """
    return _EXTENSIONS.get(mimeType, 'data')


def launchApplicationByUrl(url, mimeType):
    """Launches an application in the background for
    displaying a url which is of a specific mimeType
    @param url: the url to display
    @param mimeType: the mime type of the content
    """
    try:
        import gnomevfs
    except ImportError:
        gnomevfs = None

    try:
        from win32com.shell import shell as win32shell
    except ImportError:
        win32shell = None

    try:
        import gio
    except ImportError:
        gio = None

    if gio:
        app = gio.app_info_get_default_for_type(mimeType, True)
        if not app:
            return
        args = '%s %s' % (app.get_executable(), url)
        executable = None
        shell = True
    elif gnomevfs:
        app = gnomevfs.mime_get_default_application(mimeType)
        if not app:
            return
        args = '%s %s' % (app[2], url)
        executable = None
        shell = True
    elif win32shell:
        assoc = win32shell.AssocCreate()
        ext = _EXTENSIONS.get(mimeType)
        if ext is None:
            return
        assoc.Init(0, '.' + ext)
        args = assoc.GetString(0, _ASSOCSTR_COMMAND)
        executable = assoc.GetString(0, _ASSOCSTR_EXECUTABLE)
        args = args.replace("%1", url)
        args = args.replace("%L", url)
        shell = False
    else:
        return

    import subprocess
    subprocess.Popen(args, executable=executable,
                     shell=shell)
