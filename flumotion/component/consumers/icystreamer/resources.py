# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
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

from flumotion.component.common.streamer.mfdsresources import \
    MultiFdSinkStreamingResource


__all__ = ['ICYStreamingResource']
__version__ = "$Rev$"


class ICYStreamingResource(MultiFdSinkStreamingResource):

    def _render(self, request):
        headerValue = request.getHeader('Icy-MetaData')
        request.serveIcy = (headerValue == '1')

        return MultiFdSinkStreamingResource._render(self, request)

    def _setRequestHeaders(self, request):
        MultiFdSinkStreamingResource._setRequestHeaders(self, request)
        if request.serveIcy:
            additionalHeaders = self.streamer.get_icy_headers()

            for header in additionalHeaders:
                request.setHeader(header, additionalHeaders[header])

    def _formatHeaders(self, request):
        # Mimic Twisted as close as possible
        headers = []
        for name, value in request.headers.items():
            if not name.startswith("icy"):
                name = name.capitalize()
            headers.append('%s: %s\r\n' % (name, value))
        for cookie in request.cookies:
            headers.append('%s: %s\r\n' % ("Set-Cookie", cookie))
        return headers

    render_GET = _render
    render_HEAD = _render
