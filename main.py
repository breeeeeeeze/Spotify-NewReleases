import time
import traceback
import sys

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import PlaylistGenerator.SimpleLogger as logger
from PlaylistGenerator.PlaylistGenerator import ArtistRecentTracks, LabelRecentTracks
from PlaylistGenerator.ConfigReader import readConfig


def main():
    config = readConfig('config.ini')

    timeStart = time.time()
    # with open(config['General']['LABELS_FILE'], 'r') as inFile:
    #     labelList = inFile.read().splitlines()
    with open('labels.txt' , 'r') as inFile:
        labelList = inFile.read().splitlines()

    try:
        spotifyClient = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=config['Spotify']['CLIENT_ID'],
                client_secret=config['Spotify']['CLIENT_SECRET'],
                redirect_uri=config['Spotify']['REDIRECT_URI'],
                scope=config['Spotify']['SCOPE'],
                username=config['Spotify']['USERNAME'],
            ),
            requests_timeout=10,
            retries=10
        )

        labels = LabelRecentTracks(
            spotifyClient,
            labelList,
        )
        labels.run()

        artists = ArtistRecentTracks(
            spotifyClient
        )
        artists.run()

    except Exception:
        logger.log(traceback.format_exc(), 'error')
        sys.exit(1)

    logger.log(f'Time taken: {time.time() - timeStart}', 'info')


if __name__ == '__main__':
    main()
