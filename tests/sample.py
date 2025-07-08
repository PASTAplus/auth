import logging
import re
import subprocess
import sys
import tempfile
import json
import pathlib

HERE_PATH = pathlib.Path(__file__).parent.resolve()
TEST_FILES_PATH = HERE_PATH / 'test_files'

RUN_MELD = True

log = logging.getLogger(__name__)


active_test_files = set()


def assert_equal(received_str, filename):
    """Assert that the string is identical to the contents of the sample file"""
    expected_str = _read_file(filename)
    if received_str != expected_str:
        log.error('Received:')
        log.error(received_str)
        log.error('Expected:')
        log.error(expected_str)
        if RUN_MELD:
            is_identical = _meld(received_str, filename)
        else:
            is_identical = False
        assert is_identical, 'The received string does not match the expected string'


def assert_equal_json(received_json: str | dict, filename: str):
    """Assert that the JSON string is semantically identical to the contents of the sample file"""
    if isinstance(received_json, str):
        received_json_str = received_json
    elif isinstance(received_json, dict):
        received_json_str = json.dumps(received_json, indent=4, sort_keys=True).strip() + '\n'
    else:
        raise TypeError('received_json must be str or dict, not {}'.format(type(received_json)))
    norm_json_str = _normalize_json(received_json_str)
    expected_json_str = _read_file(filename)
    if norm_json_str != expected_json_str:
        log.error('Received JSON:')
        log.error(norm_json_str)
        log.error('Expected JSON:')
        log.error(expected_json_str)
        if RUN_MELD:
            is_identical = _meld(norm_json_str, filename)
        else:
            is_identical = False
        assert is_identical, 'The received string does not match the expected string'


def reset():
    global active_test_files
    active_test_files = set()


def status():
    log.info('Sample files used:')
    for filename in active_test_files:
        log.info('  {}'.format(filename))
    else:
        log.info('None')


def _read_file(filename):
    assert not re.match(r'test_', filename), (
        'filename should match the name of the test method, but without the "test_" prefix. '
        f'Received: "{filename}"'
    )
    assert re.search(
        r'\.json$', filename
    ), f'filename should have ".json" suffix. Received: "{filename}"'
    active_test_files.add(filename)
    file_path = TEST_FILES_PATH / filename
    if not file_path.exists():
        file_path.touch()
    return file_path.read_text()


def _normalize_json(json_str):
    return json.dumps(json.loads(json_str), indent=4, sort_keys=True).strip() + '\n'


def _meld(left_str, filename):
    """Open the meld command (apt install meld), with the contents of left_str in the left pane, and
    the contents of the named sample file in the right pane.

    :returns: The function waits until the user closes the meld window, and then returns True if the
    contents are identical, or False if not.
    """
    with tempfile.NamedTemporaryFile(delete=True, suffix='.json') as tmp_file:
        tmp_file.write(left_str.encode('utf-8'))
        tmp_file.seek(0)
        subprocess.run(('meld', tmp_file.name, (TEST_FILES_PATH / filename).as_posix()))
        tmp_file.seek(0)
        return tmp_file.read() == (TEST_FILES_PATH / filename).read_bytes()
