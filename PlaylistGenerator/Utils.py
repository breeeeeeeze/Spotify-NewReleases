import os
import re
from typing import Optional

import spotipy

from PlaylistGenerator.ConfigReader import readConfig
import PlaylistGenerator.SimpleLogger as logger

config = readConfig('config.ini')

radioShows = None
if os.path.exists(config['Filters']['FILTER_ALBUMS_FILE']):
    radioShows = open(config['Filters']['FILTER_ALBUMS_FILE']).read().splitlines()
elif config['Filters']['FILTER_ALBUMS']:
    logger.log('No album filter file found. Filtering will not work.', 'warn')

# now do the same with track filter
extendedMixes = []
if os.path.exists(config['Filters']['FILTER_TRACKS_FILE']):
    extendedMixes = open(config['Filters']['FILTER_TRACKS_FILE']).read().splitlines()
elif config['Filters']['FILTER_TRACKS']:
    logger.log('No track filter file found. Filtering will not work.', 'warn')


def isRadioshow(name: str) -> bool:
    """
    Check if album is a radio show.
    """
    if not config['Filters'].getboolean('FILTER_ALBUMS'):
        return False
    if radioShows is None:
        return False
    for el in radioShows:
        if el in name:
            return True
    return False


def isExtended(name: str) -> bool:
    """
    Check if a track is an extended version.
    """
    if not config['Filters'].getboolean('FILTER_TRACKS'):
        return False
    for el in extendedMixes:
        if el in name:
            return True
    return False


def convertToId(value: str, type_: Optional[str] = None, client: Optional[spotipy.Spotify] = None) -> str:
    """
    Take an ID, URI, URL, or name and convert it to an ID
    """
    # Possibly types
    # If it's already an ID, return it.
    if re.match(r'^[0-9a-zA-Z]{22}$', value):
        return value
    # If it's a URL, get the ID.
    if re.match(r'^https?:\/\/open.spotify.com\/((album)|(artist)|(track))\/[A-Za-z0-9]{22}\??.*$', value):
        return value.split('/')[-1]
    # If it's a URI, get the ID.
    if re.match(r'^spotify:((album)|(artist)|(track)):[A-Za-z0-9]{22}$', value):
        return value.split(':')[-1]
    if not type_:
        raise ValueError('Type of object must be specified if its not an ID, URI or URL.')
    if type_ not in ['artist', 'album', 'track']:
        raise ValueError('Invalid type of object, must be artist, album, or track')
    if not client:
        raise ValueError('Spotify client must be passed if its not an ID, URI or URL.')
    if type_ == 'artist':
        return getArtistId(value, client)
    if type_ == 'album':
        raise NotImplementedError()
    if type_ == 'track':
        raise NotImplementedError()


def getArtistId(name: str, client: spotipy.Spotify) -> str:
    """
    Get the ID of an artist.
    """
    # Get the artist ID.
    artist = client.search(name, type='artist')['artists']['items'][0]
    return artist['id']
