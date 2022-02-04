import configparser as cfg
config = cfg.ConfigParser()
config.read('config.ini')

radioShows = [el.strip() for el in config['General']['RADIOSHOWS'].split(',')]
extendedMixes = [el.strip() for el in config['General']['EXTENDED_MIXES'].split(',')]

def isRadioshow(name):
	for el in radioShows:
		if el in name:
			return True
	return False

def isExtended(name):
	for el in extendedMixes:
		if el in name:
			return True
	return False