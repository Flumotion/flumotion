# -*- Mode: Python -*-
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
#

import sys
import traceback
import xmlrpclib
import BaseHTTPServer

class RPCServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_POST(self):
        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            params, method = xmlrpclib.loads(data)
                                                                                
            # generate response
            try:
                response = self.call(method, params)
                # wrap response in a singleton tuple
                response = (response,)
            except:
                # print exception to stderr (to aid debugging)
                traceback.print_exc(file=sys.stderr)
                # report exception back to server
                fault = xmlrpclib.Fault(1, "%s:%s" % sys.exc_info()[:2])
                response = xmlrpclib.dumps(fault)
            else:
                if response[0] is None:
                    response = ('None', )
                response = xmlrpclib.dumps(response,
                                           methodresponse=1)
        except:
            # internal error, report as HTTP server error
            traceback.print_exc(file=sys.stderr)
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
 
            # shut down the connection (from Skip Montanaro)
            self.wfile.flush()
            self.connection.shutdown(1)
 
    def call(self, method, params):
	try: 
            server_method = getattr(self, method)
	except: 
            raise AttributeError, \
                  "Server does not have XML-RPC procedure %s" % method
        
        return server_method(*params)

def rpc_connect(addr):
    host, port = addr
    if host == '':
        host = 'localhost' # socket.get...()
        
    url = 'http://%s:%d/' % (host, port)
    print 'Connecting to', url
    return xmlrpclib.ServerProxy(url)
