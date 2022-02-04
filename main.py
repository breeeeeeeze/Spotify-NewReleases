

import pprint
import sys

import spotipy
from spotipy.oauth2 import SpotifyOAuth
import SimpleLogger as logger
import time
import traceback
from PlaylistGenerator import ArtistRecentTracks, LabelRecentTracks
import configparser as cfg

config = cfg.ConfigParser()
config.read('config.ini')

time_start = time.time()
playlistURIArtist = config['General']['PLAYLIST_URI_ARTISTS']
playlistURILabels = config['General']['PLAYLIST_URI_LABELS']
albumTypes = config['General']['ALBUM_TYPES']
country = config['General']['REGION']
days = int(config['General']['DAYS'])
with open(config['General']['LABELS_FILE'],'r') as f:
	labelList = f.read().splitlines()

try:
	sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=config['Spotify']['CLIENT_ID'], client_secret=config['Spotify']['CLIENT_SECRET'], redirect_uri=config['Spotify']['REDIRECT_URI'], scope=config['Spotify']['SCOPE'], username='bxtmusic'))

	labels = LabelRecentTracks(sp, labelList, playlistURI=playlistURILabels, country=country, days=days)
	labels.run()

	artists = ArtistRecentTracks(sp, playlistURI=playlistURIArtist, albumTypes=albumTypes, country=country, days=days)
	artists.run()

except Exception:
	logger.log(traceback.format_exc(), 'error')
	sys.exit(1)

logger.log(f'Time taken: {time.time() - time_start}', 'info')

