import time
import traceback
import sys
import configparser as cfg
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import SimpleLogger as logger
from PlaylistGenerator import ArtistRecentTracks, LabelRecentTracks

def main():
	config = cfg.ConfigParser()
	config.read('config.ini')

	timeStart = time.time()
	playlistURIArtist = config['General']['PLAYLIST_URI_ARTISTS']
	playlistURILabels = config['General']['PLAYLIST_URI_LABELS']
	albumTypes = config['General']['ALBUM_TYPES']
	country = config['General']['REGION']
	days = int(config['General']['DAYS'])
	with open(config['General']['LABELS_FILE'],'r') as inFile:
		labelList = inFile.read().splitlines()

	try:
		spotifyClient = spotipy.Spotify(auth_manager=SpotifyOAuth(
											client_id=config['Spotify']['CLIENT_ID'],
											client_secret=config['Spotify']['CLIENT_SECRET'],
											redirect_uri=config['Spotify']['REDIRECT_URI'],
											scope=config['Spotify']['SCOPE'],
											username=config['Spotify']['USERNAME']))

		labels = LabelRecentTracks(
									spotifyClient,
									labelList,
									playlistURI=playlistURILabels,
									country=country,
									days=days,
									config = config['General']
								)
		labels.run()

		artists = ArtistRecentTracks(
										spotifyClient,
										playlistURI=playlistURIArtist,
										albumTypes=albumTypes,
										country=country,
										days=days,
										config = config['General']
									)
		artists.run()

	except Exception:
		logger.log(traceback.format_exc(), 'error')
		sys.exit(1)

	logger.log(f'Time taken: {time.time() - timeStart}', 'info')

if __name__ == '__main__':
	main()
