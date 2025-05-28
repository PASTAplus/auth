#!/usr/bin/env bash

# exit on error
set -e

./cli/drop_and_create_db.py
./cli/add_test_profiles.py
./cli/add_test_groups.py
./cli/add_test_resources.py
