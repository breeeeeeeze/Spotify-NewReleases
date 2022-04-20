from datetime import date
from tqdm import tqdm
import SimpleLogger as logger
import Utils

class PlaylistGenerator:
	'''Playlist generator base class'''
	def __init__(self, spotify, playlistURI=None, country='DE', days=7, config=None):
		self.spotify = spotify
		self.playlistURI = playlistURI
		self.playlistTracks = []
		self.checkedAlbums = []
		self.currentDate = date.today()
		self.country = country
		self.daysSinceRelease = days
		self.artistList = []
		self.listOfAddedTracks = []
		self.userLikedTracksIds = []
		self.config = config


	def getUserLikedTracks(self):
		logger.log('Fetching list of liked tracks', 'info')
		results = self.spotify.current_user_saved_tracks(limit = 50)
		self.userLikedTracksIds.extend(results['items'])
		while results['next']:
			results = self.spotify.next(results)
			self.userLikedTracksIds.extend(results['items'])
		self.userLikedTracksIds = [track['track']['id'] for track in self.userLikedTracksIds]

	def resetPlaylist(self):
		self.spotify.playlist_replace_items(self.playlistURI, ['spotify:track:4RWkW7tGWseUu1T9LzpEBP'])
		self.spotify.playlist_remove_all_occurrences_of_items(self.playlistURI, ['spotify:track:4RWkW7tGWseUu1T9LzpEBP'])

	def checkAlbum(self, album, label=None):
		if (album['release_date_precision'] == 'day'
				and not Utils.isRadioshow(album['name'])
				and abs((self.currentDate - date.fromisoformat(album['release_date'])).days) <= self.daysSinceRelease
				and album['id'] not in self.checkedAlbums):
			try:
				albumExtended = self.spotify.album(album['id'])
			except Exception:
				logger.log('Could not fetch album ' + album['name'] + ' (' + album['id'] + ')', 'error')
				return False
			if (self.country in albumExtended['available_markets'] and
				(not label or label == albumExtended['label'])):
				self.checkedAlbums.append(album['id'])
				return True
		return False

	def getArtistList(self):
		logger.log('Fetching list of followed artists','info')
		results = self.spotify.current_user_followed_artists()
		self.artistList.extend(results['artists']['items'])
		while results['artists']['next']:
			results = self.spotify.next(results['artists'])
			self.artistList.extend(results['artists']['items'])

	def isDuplicate(self, track):
		if not self.config['IGNORE_DUPLICATES']:
			return False
		artists = ','.join(el['name'] for el in track['artists'])
		name = track['name']
		trackDict  = {artists: name}
		if trackDict in self.listOfAddedTracks:
			return True
		self.listOfAddedTracks.append(trackDict)
		return False

	def isLiked(self, track):
		if not self.config['IGNORE_ALREADY_LIKED']:
			return False
		if track['id'] in self.userLikedTracksIds:
			return True
		return False

	def artistIsFollowed(self, track):
		if not self.config['IGNORE_LABEL_IF_ARTIST_FOLLOWED']:
			return False
		artistFollowedIds = [artist['id'] for artist in self.artistList]
		for artist in track['artists']:
			if artist['id'] in artistFollowedIds:
				return True
		return False

	def checkTrack(self, track, artist=None, filterFollowedArtists=False):
		for trackArtist in track['artists']:
			if (not artist or artist['name'] == trackArtist['name']) and not Utils.isExtended(track['name']):
				if (not self.isDuplicate(track)
						and not self.isLiked(track)
						and (not filterFollowedArtists or not self.artistIsFollowed(track))):
					return True
		return False

	def addToPlaylistCache(self, track):
		self.playlistTracks.append(track['id'])
		trackArtists = []
		for trackArtist in track['artists']:
			trackArtists.append(trackArtist['name'])

	def chunkTrackList(self):
		for i in range(0, len(self.playlistTracks), 50):
			yield self.playlistTracks[i:i+50]

	def writePlaylist(self):
		logger.log('Writing playlist', 'info')
		self.resetPlaylist()
		chunkedList = list(self.chunkTrackList())
		for chunk in chunkedList:
			self.spotify.playlist_add_items(self.playlistURI, chunk)

class ArtistRecentTracks(PlaylistGenerator):
	'''Playlist generator for recent tracks of an artist'''
	def __init__(self, Spotify, playlistURI=None, albumTypes='album,single', country='DE', days=7, config=None):
		super().__init__(Spotify, playlistURI=playlistURI, country=country, days=days, config=config)
		self.albumTypes = albumTypes

	def getArtistAlbums(self, artistID):
		artistAlbumList = []
		results = self.spotify.artist_albums(artistID, limit=50, album_type=self.albumTypes, country=self.country)
		artistAlbumList.extend(results['items'])
		while results['next']:
			results = self.spotify.next(results)
			artistAlbumList.extend(results['items'])
		return artistAlbumList

	def run(self):
		self.getArtistList()
		self.getUserLikedTracks()
		logger.log('Finding recently released tracks','info')
		lelel = tqdm(self.artistList, leave=True, disable=self.config['DISABLE_PROGRESS_BAR'])
		for artist in lelel:
			lelel.set_postfix_str(artist['name'], refresh='True')
			artistAlbumList = self.getArtistAlbums(artist['id'])
			for album in artistAlbumList:
				if self.checkAlbum(album):
					tracks = self.spotify.album_tracks(album['id'])
					for track in tracks['items']:
						if self.checkTrack(track, artist):
							self.addToPlaylistCache(track)
		self.writePlaylist()

class LabelRecentTracks(PlaylistGenerator):
	'''Playlist generator for recent tracks of a label'''
	def __init__(self, Spotify, labels, playlistURI=None, country='DE', days=7, config=None):
		super().__init__(Spotify, playlistURI=playlistURI, country=country, days=days, config=config)
		if isinstance(labels, str):
			labels = list(labels)
		self.labelList = labels

	def findLabelReleases(self, label):
		labelAlbumList = []
		results = self.spotify.search(q=f'label:"{label.lower().replace(" ","+")}" tag:new', limit=10, type='album')['albums']
		labelAlbumList.extend(results['items'])
		while results['next']:
			results = self.spotify.next(results)['albums']
			labelAlbumList.extend(results['items'])
		return labelAlbumList


	def run(self):
		self.getArtistList()
		self.getUserLikedTracks()
		logger.log('Collecting releases','info')
		tqdmLabel = tqdm(self.labelList, leave=True, disable=self.config['DISABLE_PROGRESS_BAR'])
		for label in tqdmLabel:
			tqdmLabel.set_postfix_str(label, refresh="True")
			labelAlbumList = self.findLabelReleases(label)
			for album in labelAlbumList:
				if self.checkAlbum(album, label=label):
					tracks = self.spotify.album_tracks(album['id'])
					for track in tracks['items']:
						if self.checkTrack(track, filterFollowedArtists = True):
							self.addToPlaylistCache(track)
		self.writePlaylist()
