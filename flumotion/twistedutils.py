import sys
import string
from cStringIO import StringIO

from twisted.internet import reactor, protocol
from twisted.manhole.telnet import ShellFactory
from twisted.protocols import telnet
from twisted.python import log, failure

class Shell(telnet.Telnet):
    """A Python command-line shell."""
    
    def connectionMade(self):
        telnet.Telnet.connectionMade(self)
        self.lineBuffer = []
    
    def loggedIn(self):
        self.transport.write(">>> ")
    
    def checkUserAndPass(self, username, password):
        return ((self.factory.username == username) and (password == self.factory.password))

    def write(self, data):
        """Write some data to the transport.
        """
        self.transport.write(data)

    def telnet_Command(self, cmd):
        if cmd == '\x04' or cmd == 'exit':
            self.transport.loseConnection()
            return
        
        if self.lineBuffer:
            if not cmd:
                cmd = string.join(self.lineBuffer, '\n') + '\n\n\n'
                self.doCommand(cmd)
                self.lineBuffer = []
                return "Command"
            else:
                self.lineBuffer.append(cmd)
                self.transport.write("... ")
                return "Command"
        else:
            self.doCommand(cmd)
            return "Command"
    
    def doCommand(self, cmd):

        # TODO -- refactor this, Reality.author.Author, and the manhole shell
        #to use common functionality (perhaps a twisted.python.code module?)
        fn = '$telnet$'
        result = None
        try:
            out = sys.stdout
            sys.stdout = self
            try:
                code = compile(cmd,fn,'eval')
                result = eval(code, self.factory.namespace)
            except:
                try:
                    code = compile(cmd, fn, 'exec')
                    exec code in self.factory.namespace
                except SyntaxError, e:
                    if not self.lineBuffer and str(e)[:14] == "unexpected EOF":
                        self.lineBuffer.append(cmd)
                        self.transport.write("... ")
                        return
                    else:
                        failure.Failure().printTraceback(file=self)
                        #log.deferr()
                        self.write('\r\n>>> ')
                        return
                except:
                    io = StringIO()
                    failure.Failure().printTraceback(file=self)
                    #log.deferr()
                    self.write('\r\n>>> ')
                    return
        finally:
            sys.stdout = out
        
        self.factory.namespace['_'] = result
        if result is not None:
            self.transport.write(repr(result))
            self.transport.write('\r\n')
        self.transport.write(">>> ")


if __name__ == '__main__':
    log.startLogging(sys.stdout)
    ts = ShellFactory()
    ts.protocol = Shell
    reactor.listenTCP(4040, ts)
    reactor.run()
