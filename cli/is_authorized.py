#!/usr/bin/env python

"""Check if EDI token provides access to a resource.
"""

import argparse
import logging
import pprint
import sys

import requests
import urllib3

DEFAULT_IS_AUTHORIZED_ENDPOINT = 'https://localhost:5443/auth/v1/authorized'

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('token', help='EDI token')
    parser.add_argument(
        'resource_key',
        type=str,
        help='Resource key to check access for',
    )
    parser.add_argument(
        '--endpoint',
        default=DEFAULT_IS_AUTHORIZED_ENDPOINT,
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

    print(f'is_authorized(): {is_authorized(args.token, args.resource_key, args.endpoint)}')

    return 0


def is_authorized(token_str, resource_key, endpoint):
    response = requests.get(
        endpoint,
        params={
            'permission': 'read',
            'resource_key': resource_key,
        },
        cookies={
            'edi-token': token_str,
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

    return 'yes'


if __name__ == '__main__':
    sys.exit(main())
