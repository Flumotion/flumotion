# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streamer server
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
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import crypt
import md5

#########################################################
# md5crypt.py
#
# 0423.2000 by michal wallace http://www.sabren.com/
# based on perl's Crypt::PasswdMD5 by Luis Munoz (lem@cantv.net)
# based on /usr/src/libcrypt/crypt.c from FreeBSD 2.2.5-RELEASE
#
# MANY THANKS TO
#
#  Carey Evans - http://home.clear.net.nz/pages/c.evans/
#  Dennis Marti - http://users.starpower.net/marti1/
#
#  For the patches that got this thing working!
#
#########################################################
"""md5crypt.py - Provides interoperable MD5-based crypt() function

SYNOPSIS

	import md5crypt.py

	cryptedpassword = md5crypt.md5crypt(password, salt);

DESCRIPTION

unix_md5_crypt() provides a crypt()-compatible interface to the
rather new MD5-based crypt() function found in modern operating systems.
It's based on the implementation found on FreeBSD 2.2.[56]-RELEASE and
contains the following license in it:

 "THE BEER-WARE LICENSE" (Revision 42):
 <phk@login.dknet.dk> wrote this file.  As long as you retain this notice you
 can do whatever you want with this stuff. If we meet some day, and you think
 this stuff is worth it, you can buy me a beer in return.   Poul-Henning Kamp

apache_md5_crypt() provides a function compatible with Apache's
.htpasswd files. This was contributed by Bryan Hart <bryan@eai.com>.

"""

MAGIC = '$1$'			# Magic string
ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

import md5

def to64 (v, n):
    ret = ''
    while (n - 1 >= 0):
        n = n - 1
	ret = ret + ITOA64[v & 0x3f]
	v = v >> 6
    return ret


def unix_md5_crypt(pw, salt, magic=None):
    if magic==None:
        magic = MAGIC

    # Take care of the magic string if present
    if salt[:len(magic)] == magic:
        salt = salt[len(magic):]
        

    # salt can have up to 8 characters:
    import string
    salt = string.split(salt, '$', 1)[0]
    salt = salt[:8]

    ctx = pw + magic + salt

    final = md5.md5(pw + salt + pw).digest()

    for pl in range(len(pw),0,-16):
        if pl > 16:
            ctx = ctx + final[:16]
        else:
            ctx = ctx + final[:pl]


    # Now the 'weird' xform (??)

    i = len(pw)
    while i:
        if i & 1:
            ctx = ctx + chr(0)  #if ($i & 1) { $ctx->add(pack("C", 0)); }
        else:
            ctx = ctx + pw[0]
        i = i >> 1

    final = md5.md5(ctx).digest()
    
    # The following is supposed to make
    # things run slower. 

    # my question: WTF???

    for i in range(1000):
        ctx1 = ''
        if i & 1:
            ctx1 = ctx1 + pw
        else:
            ctx1 = ctx1 + final[:16]

        if i % 3:
            ctx1 = ctx1 + salt

        if i % 7:
            ctx1 = ctx1 + pw

        if i & 1:
            ctx1 = ctx1 + final[:16]
        else:
            ctx1 = ctx1 + pw
            
            
        final = md5.md5(ctx1).digest()


    # Final xform
                                
    passwd = ''

    passwd = passwd + to64((int(ord(final[0])) << 16)
                           |(int(ord(final[6])) << 8)
                           |(int(ord(final[12]))),4)

    passwd = passwd + to64((int(ord(final[1])) << 16)
                           |(int(ord(final[7])) << 8)
                           |(int(ord(final[13]))), 4)

    passwd = passwd + to64((int(ord(final[2])) << 16)
                           |(int(ord(final[8])) << 8)
                           |(int(ord(final[14]))), 4)

    passwd = passwd + to64((int(ord(final[3])) << 16)
                           |(int(ord(final[9])) << 8)
                           |(int(ord(final[15]))), 4)

    passwd = passwd + to64((int(ord(final[4])) << 16)
                           |(int(ord(final[10])) << 8)
                           |(int(ord(final[5]))), 4)

    passwd = passwd + to64((int(ord(final[11]))), 2)


    return magic + salt + '$' + passwd

def apache_md5_crypt(pw, salt):
    # change the Magic string to match the one used by Apache
    return unix_md5_crypt(pw, salt, '$apr1$')

class GateKeeper:
    pass

class HTTPGatekeeper(GateKeeper):
    def __init__(self, type):
        self.type = type
        
    def authUser(self, username, password):
        if self.type == 'md5':
            salt = passwd.split('$')[1]
            encrypted = apache_md5_crypt(password, salt)
        elif self.type == 'crypt':
            entry = self.getentry('jdahlin')
            salt = entry[:2]
            encrypted = crypt.crypt(passwd, salt)
        else:
            raise AssertionError

def createComponent(config):
    type = config.get('type', 'md5')
    
    return PasswdGate(type)

if __name__ == '__main__':
    passwd = 'amiga'
    salt = 'r1$3KmUq'
    encrypted = apache_md5_crypt(passwd, salt)
    print encrypted
