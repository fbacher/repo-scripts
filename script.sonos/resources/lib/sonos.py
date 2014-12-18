# -*- coding: utf-8 -*-
import traceback
import logging
import xbmc
import xbmcaddon

# Load the Soco classes
from soco import SoCo

__addon__ = xbmcaddon.Addon(id='script.sonos')
__icon__ = __addon__.getAddonInfo('icon')


# Use the SoCo logger
LOGGER = logging.getLogger('soco')


#########################################################################
# Sonos class to add extra support on top of SoCo
#########################################################################
class Sonos(SoCo):
    SHOWN_ERROR = False

    # Reads the current Random and repeat status
    def getPlayMode(self):
        isRandom = False
        isLoop = False
        # Check what the play mode is
        playMode = self.play_mode
        if playMode.upper() == "REPEAT_ALL":
            isLoop = True
        elif playMode.upper() == "SHUFFLE":
            isLoop = True
            isRandom = True
        elif playMode.upper() == "SHUFFLE_NOREPEAT":
            isRandom = True

        return isRandom, isLoop

    # Sets the current Random and repeat status
    def setPlayMode(self, isRandom, isLoop):
        playMode = "NORMAL"

        # Convert the booleans into a playmode
        if isRandom and isLoop:
            playMode = "SHUFFLE"
        elif isRandom and (not isLoop):
            playMode = "SHUFFLE_NOREPEAT"
        elif (not isRandom) and isLoop:
            playMode = "REPEAT_ALL"

        # Now set the playmode on the Sonos speaker
        self.play_mode = playMode

    def hasTrackChanged(self, track1, track2):
        if track2 is None:
            return False
        if track1 is None:
            return True
        if track1['uri'] != track2['uri']:
            return True
        # Don't update if the URI is the same but the new version does
        # not have event info
        if (track2['lastEventDetails'] is None) and (track1['lastEventDetails'] is not None):
            return False
        if track1['title'] != track2['title']:
            return True
        if track1['album_art'] != track2['album_art']:
            return True
        if track1['artist'] != track2['artist']:
            return True
        if track1['album'] != track2['album']:
            return True

        return False

    # Gets the most recent event from the event queue
    def getLastEventDetails(self, sub):
        queueItem = None
        try:
            # Get the most recent event received
            while not sub.events.empty():
                try:
                    # Get the next event - but do not block or wait for an event
                    # if there is not already one there
                    queueItem = sub.events.get(False)
                except:
                    LOGGER.debug("Sonos: Queue get failed: %s" % traceback.format_exc())

            # Now log the details of an event if there is one there
            if queueItem is not None:
                LOGGER.debug("Event details: %s" % queueItem)
        except:
            LOGGER.debug("Sonos: Failed to get latest event details: %s" % traceback.format_exc())

        return queueItem

    # When given a track info structure and an event, will merge the data
    # together so that it is complete and accurate
    def mergeTrackInfoAndEvent(self, track, eventDetails, previousTrack=None):
        # If there is no event data, then just return the track unchanged
        if eventDetails is None:
            # Check to see if the track has changed, if it has not, then we can
            # safely use the previous event we stored
            if (previousTrack is not None) and (track['uri'] == previousTrack['uri']) and (previousTrack['lastEventDetails'] is not None):
                LOGGER.debug("Sonos: Using previous Event details for merge")
                track['lastEventDetails'] = previousTrack['lastEventDetails']
                eventDetails = previousTrack['lastEventDetails']
            else:
                LOGGER.debug("Sonos: Event details not set for merge")
                track['lastEventDetails'] = None
                return track
        else:
            LOGGER.debug("Sonos: Event details set for merge")
            track['lastEventDetails'] = eventDetails

        # We do not want to throw an exception if we fail to process an event
        # It has been seen to happen in some strange cases, so we just catch and
        # log the error
        try:
            # Now process each part of the event message
            if eventDetails.enqueued_transport_uri_meta_data is not None:
                enqueued_transport = eventDetails.enqueued_transport_uri_meta_data
                LOGGER.debug("enqueued_transport_uri_meta_data = %s" % enqueued_transport)

                # Check if this is radio stream, in which case use that as the title
                # Station Name
                if hasattr(enqueued_transport, 'title') and (enqueued_transport.title is not None) and (enqueued_transport.title != ""):
                    if not enqueued_transport.title.startswith('ZPSTR_'):
                        if (track['title'] is None) or (track['title'] == ""):
                            track['title'] = enqueued_transport.title

            # Process the current track info
            if eventDetails.current_track_meta_data is not None:
                current_track = eventDetails.current_track_meta_data
                LOGGER.debug("current_track_meta_data = %s" % current_track)

                # Check if this is radio stream, in which case use that as the album title
                if hasattr(current_track, 'radio_show') and (current_track.radio_show is not None) and (current_track.radio_show != ""):
                    if not current_track.radio_show.startswith('ZPSTR_'):
                        if (track['album'] is None) or (track['album'] == ""):
                            track['album'] = current_track.radio_show
                            # This may be something like: Drivetime,p239255 so need to remove the last section
                            trimmed = track['album'].rpartition(',p')[0]
                            if (trimmed is not None) and (trimmed != ""):
                                track['album'] = trimmed
                # If not a radio stream then use the album tag
                elif hasattr(current_track, 'album') and (current_track.album is not None) and (current_track.album != ""):
                    if (track['album'] is None) or (track['album'] == ""):
                        track['album'] = current_track.album

                # Name of track. Can be ZPSTR_CONNECTING/_BUFFERING during transition,
                # or None if not a radio station
                if hasattr(current_track, 'stream_content') and (current_track.stream_content is not None) and (current_track.stream_content != ""):
                    if not current_track.stream_content.startswith('ZPSTR_'):
                        if (track['artist'] is None) or (track['artist'] == ""):
                            track['artist'] = current_track.stream_content
                # otherwise we have the creator to use as the artist
                elif hasattr(current_track, 'creator') and (current_track.creator is not None) and (current_track.creator != ""):
                    if (track['artist'] is None) or (track['artist'] == ""):
                        track['artist'] = current_track.creator

                # If it was a radio stream, the title will already have been set using the enqueued_transport
                if hasattr(current_track, 'title') and (current_track.title is not None) and (current_track.title != ""):
                    if not current_track.title.startswith('ZPSTR_'):
                        if (track['title'] is None) or (track['title'] == ""):
                            track['title'] = current_track.title

                # If the track has no album art, use the event one (if it exists)
                if (track['album_art'] is None) or (track['album_art'] == ""):
                    if hasattr(current_track, 'album_art_uri') and (current_track.album_art_uri is not None) and (current_track.album_art_uri != ""):
                        track['album_art'] = current_track.album_art_uri
                        # Make sure the Album art is fully qualified
                        if not track['album_art'].startswith(('http:', 'https:')):
                            track['album_art'] = 'http://' + self.ip_address + ':1400' + track['album_art']

            # Process Next Track Information
            if eventDetails.next_track_meta_data is not None:
                next_track = eventDetails.next_track_meta_data
                LOGGER.debug("next_track_meta_data = %s" % next_track)
                if hasattr(next_track, 'creator') and (next_track.creator is not None) and (next_track.creator != ""):
                    if not hasattr(track, 'next_artist') or (track['next_artist'] is None) or (track['next_artist'] == ""):
                        track['next_artist'] = next_track.creator
                if hasattr(next_track, 'album') and (next_track.album is not None) and (next_track.album != ""):
                    if not hasattr(track, 'next_album') or (track['next_album'] is None) or (track['next_album'] == ""):
                            track['next_album'] = next_track.album
                if hasattr(next_track, 'title') and (next_track.title is not None) and (next_track.title != ""):
                    if not hasattr(track, 'next_title') or (track['next_title'] is None) or (track['next_title'] == ""):
                        track['next_title'] = next_track.title
                if hasattr(next_track, 'album_art_uri') and (next_track.album_art_uri is not None) and (next_track.album_art_uri != ""):
                    if not hasattr(track, 'next_art_uri') or (track['next_art_uri'] is None) or (track['next_art_uri'] == ""):
                        track['next_art_uri'] = next_track.album_art_uri
        except:
            LOGGER.debug("Sonos: Failed to update using event details: %s" % traceback.format_exc())
            # Should really display on the screen that some of the display information
            # might not be complete of upto date, only show the error once
            if Sonos.SHOWN_ERROR is not True:
                Sonos.SHOWN_ERROR = True
                xbmc.executebuiltin('Notification(%s, %s, 5, %s)' % (__addon__.getLocalizedString(32001), __addon__.getLocalizedString(32063), __icon__))

        return track