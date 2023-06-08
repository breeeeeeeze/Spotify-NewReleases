import time

red = '\033[1;31m'
green = '\033[1;32m'
nc = '\033[0m'
blue = '\033[1;34m'
yellow = '\033[1;33m'

log_levels = {
    'debug': f'{green}[DEBUG]{nc}',
    'info': f'{blue}[INFO]{nc}',
    'warn': f'{yellow}[WARN]{nc}',
    'error': f'{red}[ERROR]{nc}',
}


def log(content: str, log_level: str = 'info'):
    if log_level not in log_levels.keys():
        raise ValueError('Invalid log level')
    if log_level == 'debug':
        return
    print(f'[{time.strftime("%y-%m-%d %H:%M:%S")}]'
          f'{log_levels[log_level]} {content}')
