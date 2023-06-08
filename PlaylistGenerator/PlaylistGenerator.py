from datetime import date
from typing import Any, Optional, Generator
from functools import cache
import shelve
import pathlib

from tqdm import tqdm
import spotipy

import PlaylistGenerator.SimpleLogger as logger
import PlaylistGenerator.Utils as Utils
from PlaylistGenerator.ConfigReader import readConfig


class PlaylistGenerator:
    '''Playlist generator base class'''

    def __init__(self, spotify: spotipy.Spotify) -> None:
        self.config = readConfig('config.ini')
        self.spotify = spotify
        self.playlistURI = None
        self.playlistTracks = []
        self.checkedAlbums = []
        self.currentDate = date.today()
        self.country = self.config['General']['REGION']
        self.daysSinceRelease = self.config['General'].getint('DAYS')
        self.artistList = []
        self.listOfAddedTracks = []
        self.userLikedTracksIds = []
        self.albumTypes: str = self.config['General']['ALBUM_TYPES']
        self.cacheFilePath = pathlib.Path(self.config['General']['CACHE_FILE']).resolve()
        if not self.cacheFilePath.parent.exists():
            self.cacheFilePath.parent.mkdir(parents=True)

    def checkPlaylistName(self, playlist, name: str, desc: str) -> bool:
        """
        Check if the correct playlist was found
        """
        if playlist['name'] == name and playlist['description'] == desc:
            return True
        return False

    def getPlaylist(self, mode: str) -> None:
        """
        Get the playlist URI, first check config, then find in users playlists, then create a new one.

        ### Parameters
            mode: Mode to use for the playlist
        """
        if mode not in ['artist', 'label']:
            raise ValueError('Invalid mode')
        modes = {'artist': 'Artists', 'label': 'Labels'}

        if self.playlistURI:
            return

        # load playlist from config
        if self.config['General'][f'PLAYLIST_URI_{modes[mode]}']:
            self.playlistURI = self.config['General'][f'PLAYLIST_URI_{modes[mode]}']
            return

        playlistName = self.config['General']['PLAYLIST_NAME'].replace('{mode}', modes[mode])
        playlistDesc = self.config['General']['PLAYLIST_DESCRIPTION']

        def searchForPlaylist(results: dict[str, Any]) -> bool:
            for playlist in results['items']:
                if self.checkPlaylistName(
                    playlist,
                    playlistName,
                    playlistDesc,
                ):
                    self.playlistURI = playlist['uri']
                    return True
            return False

        # Search for playlist in users playlists
        logger.log('Fetching or creating playlist', 'info')
        results = self.spotify.current_user_playlists()
        if searchForPlaylist(results):
            return
        while results['next']:
            if searchForPlaylist(results):
                return
        # Create playlist
        self.playlistURI = self.spotify.user_playlist_create(
            'bxtmusic',
            playlistName,
            public=False,
            description=playlistDesc,
        )['uri']

    @cache
    def getUserLikedTracks(self) -> list[str]:
        """
        Get a list of the users liked tracks from the Spotify API
        """
        if self.userLikedTracksIds:
            return
        logger.log('Fetching list of liked tracks', 'info')
        trackIds = []
        results = self.spotify.current_user_saved_tracks(limit=50)
        trackIds.extend(results['items'])
        while results['next']:
            results = self.spotify.next(results)
            trackIds.extend(results['items'])
        trackIds = [track['track']['id'] for track in trackIds]
        return trackIds

    def resetPlaylist(self) -> None:
        """
        Remove all elements in the playlist
        """
        self.spotify.playlist_replace_items(self.playlistURI, ['spotify:track:4RWkW7tGWseUu1T9LzpEBP'])
        self.spotify.playlist_remove_all_occurrences_of_items(
            self.playlistURI, ['spotify:track:4RWkW7tGWseUu1T9LzpEBP']
        )

    def checkAlbum(self, album: dict[str, Any], label: Optional[str] = None) -> bool:
        """
        Check if an album should be added to the playlist
        """
        if album is None:
            return False
        if (
            album['release_date_precision'] == 'day'
            and not Utils.isRadioshow(album['name'])
            and abs((self.currentDate - date.fromisoformat(album['release_date'])).days) <= self.daysSinceRelease
            and album['id'] not in self.checkedAlbums
            and album['album_type'] in self.albumTypes
        ):
            try:
                albumExtended = self.spotify.album(album['id'])
            except Exception:
                logger.log('Could not fetch album ' + album['name'] + ' (' + album['id'] + ')', 'error')
                return False
            if self.country in albumExtended['available_markets'] and (not label or label == albumExtended['label']):
                self.checkedAlbums.append(album['id'])
                return True
        return False

    @cache
    def getArtistList(self, artistList: Optional[list[str]] = None) -> Optional[list[Any]]:
        """
        Get a list of the artists the user follows
        """
        if self.artistList:
            return self.artistList
        logger.log('Fetching list of followed artists', 'info')
        artists = []
        results = self.spotify.current_user_followed_artists()
        artists.extend(results['artists']['items'])
        while results['artists']['next']:
            results = self.spotify.next(results['artists'])
            artists.extend(results['artists']['items'])
        return artists

    def isDuplicate(self, track: dict[str, Any]) -> bool:
        """
        Check if the track is already in the playlist
        """
        if not self.config['Filters']['IGNORE_DUPLICATES_IN_PLAYLIST']:
            return False
        artists = ','.join(el['name'] for el in track['artists'])
        name = track['name']
        trackDict = {artists: name}
        if trackDict in self.listOfAddedTracks:
            return True
        self.listOfAddedTracks.append(trackDict)
        return False

    def isLiked(self, track: dict[str, Any]) -> bool:
        """
        Check if the track is already liked by the user
        """
        if not self.config['Filters']['IGNORE_ALREADY_LIKED']:
            return False
        if track['id'] in self.userLikedTracksIds:
            return True
        return False

    def artistIsFollowed(self, track: dict[str, Any]) -> bool:
        """
        Check if the artist is followed by the user
        """
        if not self.config['Filters']['IGNORE_LABEL_IF_ARTIST_FOLLOWED']:
            return False
        artistFollowedIds = [artist['id'] for artist in self.artistList]
        for artist in track['artists']:
            if artist['id'] in artistFollowedIds:
                return True
        return False

    def checkTrack(
        self,
        track: dict[str, Any],
        /,
        *,
        artist: Optional[dict[str, Any]] = None,
        artistAlbumList: Optional[dict[str, Any]] = None,
        filterFollowedArtists: bool = False,
    ) -> bool:
        """
        Check if the track should be added to the playlist
        """
        # print(artist, artistAlbumList)
        # Check if the artist has participated on the track
        # (in case artist is tagged on album with only a single collab track)
        for trackArtist in track['artists']:
            if not artist or artist['name'] == trackArtist['name']:
                break
        else:
            return False
        if (
            not Utils.isExtended(track['name'])
            and not self.isDuplicate(track)
            and not self.isLiked(track)
            and (not filterFollowedArtists or not self.artistIsFollowed(track))
            and not self.isRerelease(track, artistAlbumList)
        ):
            return True
        return False

    @cache
    def getAdditionalData(self, albumID: str) -> dict[str, Any]:
        """
        Get additional data for an album.
        Caches results to disk to reduce API calls in the future and
        memoizes in case of multiple checks of the same album.
        """
        if albumID in self.cache:
            logger.log(f'Used cached data for {albumID}', 'debug')
            return self.cache[albumID]
        else:
            result = self.spotify.album(albumID)
            temp = result['tracks']['items']
            slimmedDict = {
                'tracks': {
                    'items': [
                        {
                            'name': el['name'],
                            'id': el['id'],
                            'artists': [{'id': elx['id'], 'name': elx['name']} for elx in el['artists']],
                        }
                        for el in temp
                    ]
                }
            }
            logger.log(f'Wrote data for album {albumID} to cache', 'debug')
            self.cache[albumID] = slimmedDict
            return slimmedDict

    def isRerelease(self, track: dict[str, Any], artistAlbumList: Optional[dict[str, Any]]) -> bool:
        """
        Check if the track is a release

        track:
            artists:
                name: str
            name: str
        """
        # logger.log(f'Checking for rereleases of {track["name"]}', 'info')
        trackArtists = [artist['name'] for artist in track['artists']]
        if not self.config['Filters']['IGNORE_RERELEASES']:
            return False
        if not artistAlbumList:
            return False
        for album in artistAlbumList:
            # make sure we don't match the track with itself or interfere with duplicate checking
            # logger.log('Checking album ' + album['name'], 'debug')
            try:
                if abs((self.currentDate - date.fromisoformat(album['release_date'])).days) <= self.daysSinceRelease:
                    # logger.log('Exit: Album is recent', 'debug')
                    continue
            # some old albums dont have the date in iso format
            except ValueError:
                continue
            # check if album has the tracks key and if not get more detailed data from the API
            if 'tracks' not in album:
                album = self.getAdditionalData(album['id'])
            for albumTrack in album['tracks']['items']:
                if not track['name'] == albumTrack['name']:
                    continue
                albumTrackArtists = [artist['name'] for artist in albumTrack['artists']]
                # print(f'{trackArtists} == {albumTrackArtists}')
                if set(trackArtists) == set(albumTrackArtists):
                    # logger.log(f'Track {track["name"]} by {trackArtists} is a rerelease', 'info')
                    return True
        # logger.log(f'Track {track["name"]} is not a rerelease', 'info')
        return False

    def addToPlaylistCache(self, track: dict[str, Any]) -> None:
        """
        add a track to the cache to be added to the playlist
        """
        self.playlistTracks.append(track['id'])
        trackArtists = []
        for trackArtist in track['artists']:
            trackArtists.append(trackArtist['name'])

    def chunkTrackList(self) -> Generator[list[dict[str, Any]], None, None]:
        """
        Split the playlist into chunks to avoid the Spotify API limit
        """
        for i in range(0, len(self.playlistTracks), 50):
            yield self.playlistTracks[i : i + 50]

    def writePlaylist(self) -> None:
        """
        Write the playlist to the Spotify API
        """
        logger.log('Writing playlist', 'info')
        self.resetPlaylist()
        chunkedList = list(self.chunkTrackList())
        for chunk in chunkedList:
            self.spotify.playlist_add_items(self.playlistURI, chunk)

    def run(self) -> None:
        self.artistList = self.getArtistList()
        self.userLikedTracksIds = self.getUserLikedTracks()


class ArtistRecentTracks(PlaylistGenerator):
    '''Playlist generator for recent tracks of an artist'''

    def __init__(self, Spotify: spotipy.Spotify) -> None:
        super().__init__(Spotify)
        self.getPlaylist('artist')

    @cache
    def getArtistAlbums(self, artistID: str) -> list[Any]:
        """
        Get a list of the albums of an artist
        """
        artistAlbumList = []
        results = self.spotify.artist_albums(artistID, limit=50, album_type=self.albumTypes, country=self.country)
        artistAlbumList.extend(results['items'])
        while results['next']:
            results = self.spotify.next(results)
            artistAlbumList.extend(results['items'])
        return artistAlbumList

    def setArtistList(self, artistList: list[str]) -> None:
        """
        Manually set the artists for which to make a recent tracks playlist
        """
        self.artistList = [{'id': artist, 'name': artist} for artist in artistList]

    def run(self) -> None:
        """
        Get the recent tracks of an artist and add them to the playlist
        """
        super().run()
        logger.log('Finding recently released tracks', 'info')
        # if there is an explicit list of artists load it
        if self.config['General'].getboolean('USE_ARTISTS_FILE'):
            if not self.ARTISTS_FILE:
                logger.log('No artists file specified. Cancelling.', 'error')
                return
            try:
                with open(self.ARTISTS_FILE, 'r') as inFile:
                    artistListRaw = inFile.read().splitlines()
            except FileNotFoundError:
                logger.log(f'Artists file "{self.ARTISTS_FILE}" not found.', 'error')
                return
            artistList = [Utils.convertToId(artist) for artist in artistListRaw]
            self.setArtistList(artistList)
        artists = tqdm(self.artistList, leave=True, disable=self.config['General'].getboolean('DISABLE_PROGRESS_BAR'))
        # start search
        try:
            self.cache = shelve.open(str(self.cacheFilePath), flag='c')
            for artist in artists:
                # get album list for each artist
                tqdmArtistString = (
                    f'{artist["name"]:<15}' if len(artist['name']) < 15 else ''.join(list(artist['name'])[:12]) + '...'
                )
                artists.set_postfix_str(tqdmArtistString, refresh=True)
                artistAlbumList = self.getArtistAlbums(artist['id'])
                for album in artistAlbumList:
                    # check each album and if it passes get tracks
                    if self.checkAlbum(album):
                        tracks = self.spotify.album_tracks(album['id'])
                        for track in tracks['items']:
                            # check each track and if it passes add it to the playlist
                            if self.checkTrack(track, artist=artist, artistAlbumList=artistAlbumList):
                                self.addToPlaylistCache(track)
        finally:
            self.cache.close()
        self.getPlaylist('artist')
        self.writePlaylist()


class LabelRecentTracks(PlaylistGenerator):
    '''Playlist generator for recent tracks of a label'''

    def __init__(
        self,
        Spotify: spotipy.Spotify,
        labels: Optional[list[str] | str] = None,
        options: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(Spotify)
        if isinstance(labels, str):
            labels = list(labels)
        self.labelList = labels
        if self.daysSinceRelease >= 14:
            logger.log(
                'Setting days above 14 may cause issues with the Spotify API and can produce incomplete results',
                'warn',
            )

    def setLabelList(self, labels: list[str]) -> None:
        """
        Set the labels for which to make a recent tracks playlist
        """
        self.labelList = labels

    def findLabelReleases(self, label: str) -> list[Any]:
        """
        Get all the labels releases
        """
        labelAlbumList = []
        newTag = 'tag: new' if self.daysSinceRelease <= 14 else ''
        results = self.spotify.search(q=f'label:"{label.lower().replace(" ","+")}" {newTag}', limit=50, type='album')[
            'albums'
        ]
        labelAlbumList.extend(results['items'])
        while results['next']:
            try:
                results = self.spotify.next(results)['albums']
                labelAlbumList.extend(results['items'])
            # TODO: Remove this try/except block when the Spotify API is fixed
            # Spotify has a search limit of 1000 and then returns a 404 error
            # Catching it here keeps the script from crashing, but can cause incomplete results
            # Keep the days at or below 14 to make use of the "new" tag
            except spotipy.exceptions.SpotifyException as err:
                if err.http_status == 404 or err.http_status == 400:
                    logger.log(
                        'Reached the Spotify search limit of 1000 for this label. '
                        'Results may be incomplete, keep the days below 15 to prevent this issue',
                        'warn',
                    )
                    break
                raise err
        return labelAlbumList

    def run(self) -> None:
        """
        Get the recent tracks of a label and add them to the playlist
        """
        super().run()
        logger.log('Collecting releases', 'info')
        tqdmLabel = tqdm(self.labelList, leave=True, disable=self.config['General'].getboolean('DISABLE_PROGRESS_BAR'))
        for label in tqdmLabel:
            tqdmLabel.set_postfix_str(label, refresh=True)
            labelAlbumList = self.findLabelReleases(label)
            for album in labelAlbumList:
                if self.checkAlbum(album, label=label):
                    tracks = self.spotify.album_tracks(album['id'])
                    for track in tracks['items']:
                        if self.checkTrack(track, filterFollowedArtists=True):
                            self.addToPlaylistCache(track)
        self.getPlaylist('label')
        self.writePlaylist()
