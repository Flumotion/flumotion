
"""Base classes handy for use with PB clients.
"""

from twisted.spread import pb
from twisted.cred import checkers, credentials

class NewCredPerspective(pb.Avatar):
    def attached(self, mind):
        pass
    def detached(self, mind):
        pass

class ReallyAllowAnonymousAccess:
    __implements__ = checkers.ICredentialsChecker

    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)

    def requestAvatarId(self, credentials):
        return credentials.username

class Username:
    __implements__ = (credentials.IUsernamePassword,)
    def __init__(self, username):
        self.username = username
        self.password = ''
        

