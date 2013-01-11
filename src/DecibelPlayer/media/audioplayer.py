# -*- coding: utf-8 -*-
#
# Author: Ingelrest François (Francois.Ingelrest@gmail.com)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import warnings
import gst

class AudioPlayer:
    """A generic GStreamer-powered audio player class"""

    ## todo: improve this, add support for events, etc.

    _player = None
    _volume = None

    def __init__(self, callbackEnded, use_playbin2=True):
        self._volume = 1.0
        self._has_replaygain = False
        self._equalizer_levels = None
        self._equalizer = None
        self._has_equalizer = False
        self._use_playbin2 = use_playbin2
        self._cd_read_speed = 1
        self.callbackEnded = callbackEnded

    @property
    def player(self):
        if self._player is None:
            self._build_player()
        return self._player

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = float(min(max(0, value), 1))
        self.player.set_property('volume', self._volume)

    def _build_player(self):
        """Create a GStreamer pipeline to be used as player"""
        if self._use_playbin2:
            self._player = gst.element_factory_make('playbin2', 'player')
            self._player.connect('about-to-finish', self._onAboutToFinish)

        else:
            self._player = gst.element_factory_make('playbin', 'player')

        ## No video
        self._player.set_property(
            'video-sink',
            gst.element_factory_make('fakesink', 'fakesink'))

        ## Restore volume
        self._player.set_property('volume', self.volume)

        ## Change the audio sink to our own bin, so that an equalizer/replay
        ## gain element can be added later on if needed
        self._audiobin  = gst.Bin('audiobin')
        self._audiosink = gst.element_factory_make('autoaudiosink', 'audiosink')

        ## Callback when the source of the playbin is changed
        self._player.connect('notify::source', self._onNewPlaybinSource)

        self._audiobin.add(self._audiosink)
        self._audiobin.add_pad(gst.GhostPad('sink', self._audiosink.get_pad('sink')))
        self._player.set_property('audio-sink', self._audiobin)

        ## Monitor messages generated by the player
        bus = self._player.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._onGstMessage)

        ## Add equalizer?
        if self._has_equalizer:
            self._equalizer = gst.element_factory_make('equalizer-10bands', 'equalizer')
            self._audiobin.add(self._equalizer)
            self._audiobin.get_pad('sink').set_target(self._equalizer.get_pad('sink'))
            self._equalizer.link(self._audiosink)

            if self._equalizer_levels is not None:
                self.setEqualizerLevels(self._equalizer_levels)

        # Add replay gain?
        if self._has_replaygain:
            replaygain = gst.element_factory_make('rgvolume', 'replaygain')

            self._audiobin.add(replaygain)
            self._audiobin.get_pad('sink').set_target(replaygain.get_pad('sink'))

            if self._equalizer is None:
                replaygain.link(self._audiosink)
            else:
                replaygain.link(self._equalizer)


    def enableEqualizer(self):
        """ Add an equalizer to the audio chain """
        self._has_equalizer = True

    def enableReplayGain(self):
        """ Add/Enable a replay gain element """
        self._has_replaygain = True

    def setEqualizerLevels(self, levels):
        """
        Set the level of the 10-bands of the equalizer (levels must be
        a list/tuple with 10 values lying between -24 and +12)
        """

        assert len(levels) == 10, "We want 10 channels"
        for level in levels:
            assert level >= -24, "Minimum accepted level is -24"
            assert level <= 12, "Maximum accepted level is +12"

        self._equalizer_levels = levels

        if self._equalizer is not None:
            self._equalizer.set_property('band0', levels[0])
            self._equalizer.set_property('band1', levels[1])
            self._equalizer.set_property('band2', levels[2])
            self._equalizer.set_property('band3', levels[3])
            self._equalizer.set_property('band4', levels[4])
            self._equalizer.set_property('band5', levels[5])
            self._equalizer.set_property('band6', levels[6])
            self._equalizer.set_property('band7', levels[7])
            self._equalizer.set_property('band8', levels[8])
            self._equalizer.set_property('band9', levels[9])


    def _onNewPlaybinSource(self, playbin, params):
        """ Change the CR-ROM drive speed to 1 when applicable """
        source = self.player.get_by_name('source')

        # Didn't find a way to determine the real class of source
        # So we use the 'paranoia-mode' property to determine whether
        # it's indeed a CD we're playing
        source.get_property('paranoia-mode')
        source.set_property('read-speed', self._cd_read_speed)
        #try:
        #    source.get_property('paranoia-mode')
        #    source.set_property('read-speed', self.cdReadSpeed)
        #except:
        #    pass


    def _onAboutToFinish(self, isLast):
        """ End of the track """
        self.callbackEnded(False)

    def _onGstMessage(self, bus, msg):
        """ A new message generated by the player """
        if msg.type == gst.MESSAGE_EOS:
            self.callbackEnded(False)
        elif msg.type == gst.MESSAGE_ERROR:
            self.stop()
            # It seems that the pipeline may not be able to play again any valid stream when an error occurs
            # We thus create a new one, even if that's quite a ugly solution
            self._build_player()
            self.callbackEnded(True)

        return True


    def setCDReadSpeed(self, speed):
        """ Set the CD-ROM drive read speed """
        self._cd_read_speed = speed


    def setNextURI(self, uri):
        """ Set the next URI """
        #self.player.set_property('uri', uri.replace('%', '%25').replace('#', '%23'))
        warnings.warn("Why setNextURI() instead of setURI() ?")
        self.setURI(uri)


    def setVolume(self, level):
        """ Set the volume to the given level (0 <= level <= 1) """
        self.volume = level


    def isPaused(self):
        """ Return whether the player is paused """
        return self.player.get_state()[1] == gst.STATE_PAUSED


    def isPlaying(self):
        """ Return whether the player is paused """
        return self.player.get_state()[1] == gst.STATE_PLAYING


    def setURI(self, uri):
        """ Play the given URI """
        ## why this kind-of url-encoding?
        #self.player.set_property('uri', uri.replace('%', '%25').replace('#', '%23'))
        self.player.set_property('uri', uri)


    def play(self):
        """ Play """
        self.player.set_state(gst.STATE_PLAYING)


    def pause(self):
        """ Pause """
        self.player.set_state(gst.STATE_PAUSED)


    def stop(self):
        """ Stop playing """
        self.player.set_state(gst.STATE_NULL)


    def seek(self, where):
        """ Jump to the given location """
        self.player.seek_simple(gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, where)


    def getPosition(self):
        """ Return the current position """
        return self.player.query_position(gst.FORMAT_TIME)[0]
        #try:
        #    return self.player.query_position(gst.FORMAT_TIME)[0]
        #except:
        #    ## why??
        #    return 0


    def getDuration(self):
        """ Return the duration of the current stream """
        return self.player.query_duration(gst.FORMAT_TIME)[0]
        #try:
        #    return self.player.query_duration(gst.FORMAT_TIME)[0]
        #except:
        #    return 0
