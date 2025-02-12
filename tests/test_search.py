#!/usr/bin/env python

import logging
import sys
import heapq
import random

log = logging.getLogger(__name__)

# For benchmarking
C = 1

KEY_TUP = ('william', 'thomas', 'william@thomas.com')

search_str = 'willx'


def count_shared_chars(search_str, key_tup):
    for k in key_tup:
        print(k, sum(100 for c1, c2 in zip(search_str, k) if c1 == c2) - len(search_str))

    return max(
        sum(100 for c1, c2 in zip(k, search_str) if c1 == c2) - len(search_str)
        for k in key_tup
    )


def main():
    r_list = [random.randint(1, 10000) for _ in range(10000)]
    n = heapq.nlargest(5, r_list)
    print(n)

    # h = heapq.


    # while True:
    #     print(KEY_TUP)
    #     search_str = input('Search str: ')
    #     score = 0
    #     for _ in range(C):
    #         score += count_shared_chars(search_str, KEY_TUP)
    #
    #     print(score / C)


if __name__ == '__main__':
    sys.exit(main())
