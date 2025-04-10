#!/usr/bin/env bash

set -e # exit on error

./cli/clear_database.py
./cli/add_test_profiles.py
./cli/add_test_groups.py
./cli/add_test_permissions.py
./cli/add_test_groups.py

