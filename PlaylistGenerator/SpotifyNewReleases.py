import configparser as cfg

import spotipy

import PlaylistGenerator.SimpleLogger as logger
from PlaylistGenerator.PlaylistGenerator import ArtistRecentTracks, LabelRecentTracks
from PlaylistGenerator.ConfigReader import readConfig
import PlaylistGenerator.Utils as Utils


class SpotifyNewReleases:
    def __init__(self, /, *, configFilename: str = 'config.ini'):
        self.configFilename = configFilename
        self.config = self.loadConfig()

        # Spotify API credentials
        self.CLIENT_ID = self.config['Spotify']['CLIENT_ID']
        self.CLIENT_SECRET = self.config['Spotify']['CLIENT_SECRET']
        self.REDIRECT_URI = self.config['Spotify']['REDIRECT_URI']
        self.SCOPE = self.config['Spotify']['SCOPE']
        self.USERNAME = self.config['Spotify']['USERNAME']

        # Config
        self.LABELS_FILE = self.config['General']['LABELS_FILE']
        self.ARTISTS_FILE = self.config['General']['ARTISTS_FILE']
        self.USE_ARTISTS_FILE = self.config['General'].getboolean('USE_ARTISTS_FILE')
        self.PLAYLIST_URI_ARTISTS = self.config['General']['PLAYLIST_URI_ARTISTS']
        self.PLAYLIST_URI_LABELS = self.config['General']['PLAYLIST_URI_LABELS']
        self.PLAYLIST_NAME = self.config['General']['PLAYLIST_NAME']
        self.PLAYLIST_DESCRIPTION = self.config['General']['PLAYLIST_DESCRIPTION']
        self.PLAYLIST_IMAGE = self.config['General']['PLAYLIST_IMAGE']
        self.ALBUM_TYPES = self.config['General']['ALBUM_TYPES']
        self.REGION = self.config['General']['REGION']
        self.DAYS = self.config['General']['DAYS']
        self.DISABLE_PROGRESS_BAR = self.config['General'].getboolean('DISABLE_PROGRESS_BAR')

        # Filters
        self.FILTER_ALBUMS = self.config['Filters'].getboolean('FILTER_ALBUMS')
        self.FILTER_TRACKS = self.config['Filters'].getboolean('FILTER_LABELS')
        self.FILTER_ALBUMS_FILE = self.config['Filters']['FILTER_ALBUMS_FILE']
        self.FILTER_TRACKS_FILE = self.config['Filters']['FILTER_TRACKS_FILE']
        self.IGNORE_DUPLICATES = self.config['Filters'].getboolean('IGNORE_DUPLICATES')
        self.IGNORE_ALREADY_LIKED = self.config['Filters'].getboolean('IGNORE_ALREADY_LIKED')
        self.IGNORE_LABEL_IF_ARTIST_FOLLOWED = self.config['Filters'].getboolean('IGNORE_LABEL_IF_ARTIST_FOLLOWED')


    def loadConfig(self) -> cfg.ConfigParser:
        return readConfig(self.configFilename)

    def run(self, modes: list[str] | str) -> None:
        self.spotify = spotipy.Spotify(
            auth_manager=spotipy.oauth2.SpotifyOAuth(
                client_id=self.CLIENT_ID,
                client_secret=self.CLIENT_SECRET,
                redirect_uri=self.REDIRECT_URI,
                scope=self.SCOPE,
                username=self.USERNAME,
            )
        )
        if 'artists' in modes:
            self.runArtist()
        if 'labels' in modes:
            self.runLabel()

    def runArtist(self) -> None:
        art = ArtistRecentTracks(self.spotify)
        if self.USE_ARTISTS_FILE:
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
            art.setArtistList(artistList)
            logger.log('Manually set artist list', 'info')
        logger.log('Creating playlist with artists recent releases.', 'info')
        art.run()

    def runLabel(self) -> None:
        try:
            with open(self.LABELS_FILE) as inFile:
                labelList = inFile.read().splitlines()
        except FileNotFoundError:
            logger.log(f'Labels file "{self.LABELS_FILE}" not found.', 'error')
            return
        label = LabelRecentTracks(self.spotify, labelList)
        logger.log('Creating playlist with labels recent releases.', 'info')
        label.run()
         
