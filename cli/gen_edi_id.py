#!/usr/bin/env python

"""Generate a randomized EDI-ID."""
import pathlib
import sys

BASE_PATH = pathlib.Path(__file__).resolve().parent.parent
sys.path.append((BASE_PATH / 'webapp').as_posix())

import util.edi_id


def main():
    print(util.edi_id.get_random_edi_id())
    return 0


if __name__ == '__main__':
    sys.exit(main())
