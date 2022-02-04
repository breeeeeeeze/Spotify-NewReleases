from datetime import date
import SimpleLogger as logger
import Utils
from tqdm import tqdm

class PlaylistGenerator:
	def __init__(self, Spotify, playlistURI=None, country='DE', days=7):
		self.Spotify = Spotify
		self.playlistURI = playlistURI
		self.playlistTracks = []
		self.checkedAlbums = []
		self.currentDate = date.today()
		self.country = country
		self.daysSinceRelease = days

	def resetPlaylist(self):
		self.Spotify.playlist_replace_items(self.playlistURI, ['spotify:track:4RWkW7tGWseUu1T9LzpEBP'])
		self.Spotify.playlist_remove_all_occurrences_of_items(self.playlistURI, ['spotify:track:4RWkW7tGWseUu1T9LzpEBP'])

	def checkAlbum(self, album, label=None):
		if ( album['release_date_precision'] == 'day' and
			not Utils.isRadioshow(album['name']) and
			abs((self.currentDate - date.fromisoformat(album['release_date'])).days) <= self.daysSinceRelease and
			album['id'] not in self.checkedAlbums):
			album_extended = self.Spotify.album(album['id'])
			if ( self.country in album_extended['available_markets'] and
				(not label or label == album_extended['label'])):
				self.checkedAlbums.append(album['id'])
				return True
		return False

	def checkTrack(self, track, artist=None):
		for a in track['artists']:
			if (not artist or artist['name'] == a['name']) and not Utils.isExtended(track['name']):
				return True
		return False

	def addToPlaylistCache(self, track):
		self.playlistTracks.append(track['id'])
		track_artists = []
		for a in track['artists']:
			track_artists.append(a['name'])
		#logger.log(f'{", ".join(track_artists)} - {track["name"]} added', 'debug')

	def chunkTrackList(self):
		for i in range(0, len(self.playlistTracks), 50):
			yield self.playlistTracks[i:i+50]

	def writePlaylist(self):
		logger.log('Writing playlist', 'info')
		self.resetPlaylist()
		chunkedList = list(self.chunkTrackList())
		for el in chunkedList:
			self.Spotify.playlist_add_items(self.playlistURI, el)
							
class ArtistRecentTracks(PlaylistGenerator):
	def __init__(self, Spotify, playlistURI=None, albumTypes='album,single', country='DE', days=7):
		super().__init__(Spotify, playlistURI=playlistURI, country=country, days=days)
		self.artistList = []
		self.albumTypes = albumTypes

	def getArtistList(self):
		logger.log('Getting list of followed artists','info')
		results = self.Spotify.current_user_followed_artists()
		self.artistList.extend(results['artists']['items'])
		while results['artists']['next']:
			results = self.Spotify.next(results['artists'])
			self.artistList.extend(results['artists']['items'])

	def getArtistAlbums(self, artistID):
		artistAlbumList = []
		results = self.Spotify.artist_albums(artistID, limit=50, album_type=self.albumTypes, country=self.country)
		artistAlbumList.extend(results['items'])
		while results['next']:
			results = self.Spotify.next(results)
			artistAlbumList.extend(results['items'])
		return artistAlbumList

	def run(self):
		self.getArtistList()
		logger.log('Finding recently released track','info')
		lelel = tqdm(self.artistList, leave=True)
		for artist in lelel:
			lelel.set_postfix_str(artist['name'], refresh='True')
			artistAlbumList = self.getArtistAlbums(artist['id'])
			for album in artistAlbumList:
				if self.checkAlbum(album):
					tracks = self.Spotify.album_tracks(album['id'])
					for track in tracks['items']:
						if self.checkTrack(track, artist):
							self.addToPlaylistCache(track)
		self.writePlaylist()

class LabelRecentTracks(PlaylistGenerator):
	def __init__(self, Spotify, labels, playlistURI=None, country='DE', days=7):
		super().__init__(Spotify, playlistURI=playlistURI, country=country, days=days)
		if isinstance(labels, str):
			labels = list(labels)
		self.labelList = labels

	def findLabelReleases(self, label):
		#logger.log(f'Finding albums for {label}', 'info')
		labelAlbumList = []
		results = self.Spotify.search(q=f'label:"{label.lower().replace(" ","+")}" tag:new', limit=10, type='album')['albums']
		labelAlbumList.extend(results['items'])
		while results['next']:
			results = self.Spotify.next(results)['albums']
			labelAlbumList.extend(results['items'])
		return labelAlbumList
			

	def run(self):
		logger.log('Collecting releases','info')
		tqdm_label = tqdm(self.labelList, leave=True)
		for label in tqdm_label:
			tqdm_label.set_postfix_str(label, refresh="True")
			labelAlbumList = self.findLabelReleases(label)
			for album in labelAlbumList:
				if self.checkAlbum(album, label=label):
					tracks = self.Spotify.album_tracks(album['id'])
					for track in tracks['items']:
						if self.checkTrack(track):
							self.addToPlaylistCache(track)
		self.writePlaylist()
