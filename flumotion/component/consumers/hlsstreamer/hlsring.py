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

import os
from collections import deque

from Crypto.Cipher import AES

from twisted.internet import reactor
from flumotion.component.consumers.hlsstreamer import common


class Playlister:
    """
    I write HTTP Live Streaming playlists based on added fragments.
    """

    def __init__(self):
        self._hostname = ''
        self.mainPlaylist = ''
        self.streamPlaylist = ''
        self.streamBitrate = 0
        self.title = ''
        self.fragmentPrefix = ''
        self.newFragmentTolerance = 0
        self.window = 0
        self.keysURI = ''
        self.filenameExt = 'webm'
        #FIXME: Make it a property
        self.allowCache = True
        self._fragments = []
        self._dummyFragments = []
        self._counter = 0
        self._isAutoUpdate = False

    def setHostname(self, hostname):
        if hostname.startswith('/'):
            hostname = hostname[1:]
        if not hostname.endswith('/'):
            hostname = hostname + '/'
        if not hostname.startswith('http://'):
            hostname = 'http://' + hostname
        self._hostname = hostname

    def setAllowCache(self, allowed):
        self.allowCache = allowed

    def _getFragmentName(self, sequenceNumber):
        return '%s-%s.%s' % (self.fragmentPrefix, sequenceNumber,
                             self.filenameExt)

    def _getTargetDuration(self):
        sorted_list = sorted(self._fragments, key=lambda fragment: fragment[1])
        return int(sorted_list[0][1])

    def _autoUpdate(self, count):
        if self._counter == count:
            self._isAutoUpdate = True
            self._dummyFragments.append(self._getFragmentName(count))
            self._addPlaylistFragment(count, self._duration, False)

    def _addPlaylistFragment(self, sequenceNumber, duration, encrypted):
        # Add the fragment to the playlist if it wasn't added before
        if not sequenceNumber in [frag[0] for frag in self._fragments]:
            # Add a discontinuity if the sequenceNumber is not the expected
            self._fragments.append((sequenceNumber, duration, encrypted,
                sequenceNumber != self._counter and self._counter != 0))
            self._counter = sequenceNumber + 1
            # Remove fragments that are out of the window
            while len(self._fragments) > self.window:
                # If it's a dummy fragment, remove it from the list too
                fragName = self._getFragmentName(self._fragments[0][0])
                if fragName in self._dummyFragments:
                    self._dummyFragments.remove(fragName)
                del self._fragments[0]

        # Auto update the playlist when the next fragment was not added
        # If the fragment was automatically added update again after 'duration'
        if self.newFragmentTolerance != 0:
            reactor.callLater(self._isAutoUpdate and
                    duration or duration * (1 + self.newFragmentTolerance),
                    self._autoUpdate, self._counter)
        self._isAutoUpdate= False

        return self._getFragmentName(sequenceNumber)

    def renderArgs(self, args):
        if 'FLUREQID' in args:
            del args['FLUREQID']
        if len(args) == 0:
            return ''

        return '?' + '&'.join(["%s=%s" % (k, v[0]) for k, v in
                              args.iteritems()])

    def _renderMainPlaylist(self, args):
        lines = []

        lines.append("#EXTM3U")
        #The bandwith value is not significant for single bitrate
        lines.append("#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=%s" %
                self.streamBitrate)
        lines.append("".join([self._hostname, self.streamPlaylist,
            self.renderArgs(args)]))
        lines.append("")

        return "\n".join(lines)

    def _renderStreamPlaylist(self, args):
        lines = []

        lines.append("#EXTM3U")
        lines.append("#EXT-X-ALLOW-CACHE:%s" %
                (self.allowCache and 'YES' or 'NO'))
        lines.append("#EXT-X-TARGETDURATION:%d" % self._getTargetDuration())
        lines.append("#EXT-X-MEDIA-SEQUENCE:%s" % self._fragments[0][0])

        for sequenceNumber, duration, encrypted, discon in self._fragments:
            if discon:
                lines.append("#EXT-X-DISCONTINUITY")
            # FIXME: Not fully implemented yet
            if encrypted:
                lines.append('#EXT-X-KEY:METHOD=AES-128,URI="%s?key=%s"' %
                        (self.keysURI, fragment))
            lines.append("#EXTINF:%d,%s" % (duration, self.title))
            lines.append(''.join([self._hostname,
                self._getFragmentName(sequenceNumber), self.renderArgs(args)]))

        lines.append("")

        return "\n".join(lines)

    def renderPlaylist(self, playlist, args):
        '''
        Returns a string representation of the requested playlist or raise
        an Exception if the playlist is not found
        '''
        if playlist == self.mainPlaylist:
            return self._renderMainPlaylist(args)
        elif playlist == self.streamPlaylist:
            return self._renderStreamPlaylist(args)
        raise common.PlaylistNotFound()


class HLSRing(Playlister):
    '''
    I hold a ring with the fragments available in the playlist
    and update the playlist according to this.
    '''

    BLOCK_SIZE = 16
    PADDING = '0'

    def __init__(self, mainPlaylist, streamPlaylist,
            streamBitrate=300000, title='', fragmentPrefix='mpegts',
            newFragTolerance = 0, window=5, maxExtraBuffers=None,
            keyInterval=0, keysURI=None):
        '''
        @param mainPlaylist:    resource name of the main playlist
        @type  mainPlaylist:    str
        @param streamPlaylists: resource names of the playlists
        @type  streamPlaylist:  str
        @param streamBitrate:   Bitrate of the stream in bps
        @type  streamBitrate:   int
        @param title:           description of the stream
        @type  title:           str
        @param fragmentPrefix:  fragment name prefix
        @type  fragmentPrefix:  str
        @param newFragTolerance:Tolerance to automatically add new fragments.
        @type  newFragTolerance:float
        @param window:          maximum number of fragments to buffer
        @type  window:          int
        @param maxExtraBuffers: maximum number of extra fragments to buffer
        @type  maxExtraBuffers: int
        @param keyInterval:     number of fragments sharing the same encryption
                                key. O if not using encryption
        @type  keyInterval:     int
        @param keysURI          URI used to retrieve the encription keys
        @type  keysURI          str
        '''

        Playlister.__init__(self)
        self.mainPlaylist = mainPlaylist
        self.streamPlaylist = streamPlaylist
        self.streamBitrate = streamBitrate
        self.title = title
        self.fragmentPrefix = fragmentPrefix
        self.newFragmentTolerance = newFragTolerance
        self.window = window
        if maxExtraBuffers is None:
            self.maxBuffers = 2 * window +1
        else:
            self.maxBuffers = window + maxExtraBuffers
        self.keyInterval = keyInterval
        self.keysURI = keysURI or self._hostname
        self._encrypted = (keyInterval != 0)
        self._fragmentsDict = {}
        self._keysDict = {}
        self._secret = ''
        self._availableFragments = deque('')
        self._lastSequence = None

    def _encryptFragment(self, fragment, secret, IV):
        # FIXME: Not tested
        right_pad = lambda s: s + (self.BLOCK_SIZE -len(s) % self.BLOCK_SIZE)\
                * self.PADDING
        left_pad = lambda s: (self.BLOCK_SIZE -len(s) % self.BLOCK_SIZE)\
                * self.PADDING + s
        EncodeAES = lambda c, s: c.encrypt(right_pad(s))

        cipher = AES.new(secret, AES.MODE_CBC, left_pad(str(IV)))
        return EncodeAES(cipher, fragment)

    def reset(self):
        self._fragmentsDict = {}
        self._keysDict = {}
        self._secret = ''
        self._availableFragments = deque('')
        self._fragments = []
        self._dummyFragments = []
        self._lastSequence = None
        self._counter = 0

    def addFragment(self, fragment, sequenceNumber, duration):
        '''
        Adds a fragment to the ring and updates the playlist.
        If the ring is full, removes the oldest fragment.

        @param fragment:        mpegts raw fragment
        @type  fragment:        array
        @param sequenceNumber:  sequence number relative to the stream's start
        @type  sequenceNumber:  int
        @param duration:        duration of the the segment in seconds
        @type  duration:        int

        @return:                the name used in the playlist for the fragment
        @rtype :                str
        '''

        # We only care about the name used in the playlist, we let the
        # playlister name it using an appropiate extension
        fragmentName = self._addPlaylistFragment(sequenceNumber, duration,
                self._encrypted)
        # Don't add duplicated fragments
        if fragmentName in self._availableFragments:
            return
        self._lastSequence = sequenceNumber

        # If the ring is full, delete the oldest segment.
        while len(self._fragmentsDict) >= self.maxBuffers:
            pop = self._availableFragments.popleft()
            del self._fragmentsDict[pop]
            if pop in self._keysDict:
                del self._keysDict[pop]

        self._availableFragments.append(fragmentName)
        if self._encrypted:
            if sequenceNumber % self.keyInterval == 0:
                self._secret = os.urandom(self.BLOCK_SIZE)
            fragment = self._encryptFragment(fragment, self._secret,
                    sequenceNumber)
            self._keysDict[fragmentName] = self._secret
        self._fragmentsDict[fragmentName] = fragment
        return fragmentName

    def getFragment(self, fragmentName):
        '''
        Returns a fragment of the playlist or raises an Exception
        if the fragment is not found

        @param fragmentName:    name of the fragment to retrieve
        @type  fragmentName:    str

        @return:                an mpegts raw fragment
        @rtype:                 array
        '''

        if fragmentName in self._fragmentsDict:
            return self._fragmentsDict[fragmentName]
        if fragmentName in self._dummyFragments:
            raise common.FragmentNotAvailable()
        raise common.FragmentNotFound()

    def getEncryptionKey(self, key):
        '''
        Returns an encryption key from the keys dict or raises an
        Exception if the key is not found

        @param key:     name of the key to retrieve
        @type  key:     str

        @return:        the encryption key
        @rtype:         str
        '''

        if key in self._keysDict:
            return self._keysDict[key]
        raise common.KeyNotFound()
