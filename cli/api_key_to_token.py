#!/usr/bin/env python

"""Exchange an API key for an EDI token.
"""

import argparse
import logging
import pprint
import sys

import requests
import urllib3

DEFAULT_KEY_TO_TOKEN_ENDPOINT = 'https://localhost:5443/auth/v1/key'

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'api_key',
        type=str,
        help='API key to exchange for an EDI token',
    )
    parser.add_argument(
        '--endpoint',
        default=DEFAULT_KEY_TO_TOKEN_ENDPOINT,
        help='The endpoint to use (default: %(default)s)',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging',
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    edi_token = key_to_token(args.api_key, args.endpoint)
    if edi_token is None:
        return 1

    # Print human-friendly output to a terminal, raw token when piped
    if sys.stdout.isatty():
        print(f'EDI Token: {edi_token}')
    else:
        sys.stdout.write(edi_token + '\n')

    return 0


def key_to_token(api_key, endpoint):
    response = requests.post(
        endpoint,
        json={
            'key': api_key,
        },
        # Disable SSL verification for local testing
        verify=False,
    )
    try:
        response_dict = response.json()
    except ValueError:
        log.error(f'Error: HTTP {response.status_code}: Response is not valid JSON')
        log.error(pprint.pformat(response.text))
        return None

    if response.status_code != 200:
        log.error(f'Error: HTTP {response.status_code}')
        log.error(pprint.pformat(response_dict))
        return None

    return response.json()['edi-token']


if __name__ == '__main__':
    sys.exit(main())
