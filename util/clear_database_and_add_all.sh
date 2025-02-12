#!/usr/bin/env bash

set -e # exit on error

./util/clear_database.py
./util/add_test_profiles.py
./util/add_test_groups.py
./util/add_test_permissions.py

