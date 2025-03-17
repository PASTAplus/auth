#!/usr/bin/env python

"""Decode and print a PASTA token"""
import argparse
import sys
import base64

import daiquiri

log = daiquiri.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('token', help='PASTA token')
    args = parser.parse_args()

    token_b64, token_signature_b64 = args.token.split('-')
    token_str = base64.b64decode(token_b64).decode('utf-8')

    print(token_str)


if __name__ == '__main__':
    sys.exit(main())
