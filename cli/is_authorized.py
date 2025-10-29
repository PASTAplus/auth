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
        '--permission',
        default='read',
        choices=['read', 'write', 'changePermission'],
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

    is_authorized = get_is_authorized(args.token, args.resource_key, args.permission, args.endpoint)
    print(f'is_authorized(): {"yes" if is_authorized else "no"}')

    return 0


def get_is_authorized(token_str, resource_key, permission_str, endpoint):
    response = requests.get(
        endpoint,
        params={
            'permission': permission_str,
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
        return False

    if response.status_code != 200:
        log.error(f'Error: HTTP {response.status_code}')
        log.error(pprint.pformat(response_dict))
        return False

    return True


if __name__ == '__main__':
    sys.exit(main())
