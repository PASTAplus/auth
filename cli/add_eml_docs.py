#!/usr/bin/env python

"""Add EML documents for testing.

- This uses the AddEML API.
- If the path to a directory tree is provided, this will recursively search for EML documents named
Level-1-EML.xml and add them to the running EDI IAM instance (local by default).
- If the path to a single EML document is provided, it will add just that document.
- The token profile must be a member of the Vetted system group.
- The token profile becomes the owner of all the resources created from the EML document. This
differs from production, where EML document are usually owned by their uploading profiles.
"""

import argparse
import logging
import pathlib
import pprint
import sys

import requests
import urllib3

DEFAULT_ADD_EML_ENDPOINT = 'https://localhost:5443/auth/v1/eml'

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'token_path',
        type=pathlib.Path,
        help='Path to file containing EDI token',
    )
    parser.add_argument(
        'eml_path',
        type=pathlib.Path,
        help='Path to an EML document, or to the root of a directory tree containing EML files',
    )
    parser.add_argument(
        '--key_prefix',
        help='Prefix for the metadata resources (default: %(default)s)',
        default='https://localhost',
    )
    parser.add_argument(
        '--endpoint',
        default=DEFAULT_ADD_EML_ENDPOINT,
        help='The endpoint to use for adding EML documents (default: %(default)s)',
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

    token_str = args.token_path.read_text()

    if args.eml_path.is_file():
        return add_eml(token_str, args, args.eml_path)
    elif args.eml_path.is_dir():
        add_eml_from_directory_tree(token_str, args)
        return 0
    else:
        log.error(f'Path is not a file or directory: {args.eml_path.as_posix()}')
        return 1


def add_eml_from_directory_tree(token_str, args):
    for eml_path in args.eml_path.rglob('Level-1-EML.xml'):
        add_eml(token_str, args, eml_path)


def add_eml(token_str, args, eml_path):
    log.info(
        f'Adding EML document: {eml_path.as_posix()}',
    )
    response = requests.post(
        args.endpoint,
        json={
            'eml': eml_path.read_text(),
            'key_prefix': args.key_prefix,
        },
        cookies={
            'edi-token': token_str,
        },
        # Disable SSL verification for local testing
        verify=False,
    )
    if response.status_code != 200:
        log.error(f'Failed to add EML document - HTTP {response.status_code}')
        log.error(pprint.pformat(response.json()))
        return 1

    log.info('EML document added successfully')
    log.info(pprint.pformat(response.json()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
