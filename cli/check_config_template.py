#!/usr/bin/env python

"""Check that the config.py.template file is up to date with the current config.py file.
"""

import logging
import pathlib
import sys

CONF_PATH = pathlib.Path(__file__).resolve().parent.parent / 'webapp' / 'config.py'
TEMPLATE_PATH = CONF_PATH.with_name('config.py.template')

log = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG)

    conf_set = read_conf(CONF_PATH)
    template_set = read_conf(TEMPLATE_PATH)

    log.info('Checking config.py against config.py.template...')
    log.info(f'  {CONF_PATH}')
    log.info(f'  {TEMPLATE_PATH}')

    template_missing_set = conf_set - template_set
    template_extra_set = template_set - conf_set
    if template_missing_set:
        log.error('The following settings are missing from the template:')
        for key in sorted(template_missing_set):
            log.error(f'  {key}')
    else:
        log.info('No settings are missing from the template.')

    if template_extra_set:
        log.error('The following settings are extra in the template:')
        for key in sorted(template_extra_set):
            log.error(f'  {key}')
    else:
        log.info('No extra settings in the template.')

def read_conf(path):
    """Read the config file and return a dictionary of the config values."""
    settings_set = set()
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _ = line.split('=', 1)
            key = key.strip()
            if key != key.upper():
                continue
            settings_set.add(key)
    return settings_set


if __name__ == '__main__':
    sys.exit(main())
