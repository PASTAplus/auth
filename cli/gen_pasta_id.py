#!/usr/bin/env python

"""Generate a EDI-ID random unique identifier."""

import sys
import uuid

def main():
    print(f'EDI-{uuid.uuid4().hex}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
