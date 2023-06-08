import sys
import configparser as cfg

import PlaylistGenerator.SimpleLogger as logger


def readConfig(filename):
    """
    Reads the config file and returns a config parser object.
    """
    config = cfg.ConfigParser(inline_comment_prefixes=('#'))
    try:
        config.read(filename)
    except FileNotFoundError:
        logger.log(f'Config file "{filename}" not found.', 'error') 
        sys.exit(1)
    return config
