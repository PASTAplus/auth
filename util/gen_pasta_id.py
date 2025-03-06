#!/usr/bin/env python

"""Generate a PASTA-ID random unique identifier."""

import sys
import uuid

def main():
    print(f'PASTA-{uuid.uuid4().hex}')

if __name__ == '__main__':
    sys.exit(main())
