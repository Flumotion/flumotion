import pygtk
pygtk.require('2.0')

# Install reactor, should move somewhere
from flumotion.twisted import gstreactor
gstreactor.install()

# monkey patching twisted doc errors
from twisted.spread import pb
def login(self, credentials, client=None):
	"""Login and get perspective from remote PB server.

	Currently only credentials implementing IUsernamePassword are
	supported.

	@return: Deferred of RemoteReference to the perspective."""
def getRootObject(self):
	"""Get root object of remote PB server.

        @return: Deferred of the root object.
        """
def getPerspective(self, username, password, serviceName,
                       perspectiveName=None, client=None):
        """Get perspective from remote PB server.

        New systems should use login() instead.
        
        @return: Deferred of RemoteReference to the perspective.
        """

pb.PBClientFactory.login = login
pb.PBClientFactory.getRootObject = getRootObject 
pb.PBClientFactory.getPerspective = getPerspective

from epydoc.cli import cli
cli()
