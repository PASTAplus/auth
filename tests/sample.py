"""Compare the output of tests with sample files.

If `RUN_MELD` is set to `False`, the code will only log the differences.

If `RUN_MELD` is set to `True`, the code will open the `meld` command with the contents of the
received string in the left pane, and the contents of the sample file in the right pane. The user
can then visually compare the two and update the sample file if desired. When the user closes the
meld window, the code will return `True` if the contents are identical, or `False` if not, which
will then cause the test to pass or fail respectively.

Install the `meld` command with `apt install meld`.
"""

import difflib
import json
import logging
import pathlib
import re
import subprocess
import tempfile

import util.pretty

HERE_PATH = pathlib.Path(__file__).parent.resolve()
TEST_FILES_PATH = HERE_PATH / 'test_files'

RUN_MELD = False

log = logging.getLogger(__name__)


active_test_files = set()


def assert_match(received_obj: str | dict | set | list, filename: str, clobber=False):
    """Assert that the received object matches the expected JSON in the given sample file.
    We encode objects to normalized JSON before comparing.
    """
    if clobber:
        _clobber_edi_ids(received_obj)
    norm_json_str = _to_normalized_json(received_obj)
    expected_json_str = _read_file(filename)
    if norm_json_str != expected_json_str:
        log.error('Received JSON:')
        log.error(norm_json_str)
        log.error('Expected JSON:')
        log.error(expected_json_str)
        if RUN_MELD:
            is_identical = _meld(norm_json_str, filename)
        else:
            dump_diff(norm_json_str, expected_json_str)
            is_identical = False
        assert is_identical, 'The received string does not match the expected string'


def dump_diff(current_str, sample_str):
    """Dump a diff between the received object and the expected JSON."""
    print(
        'Sample mismatch.\nActual:\n{}\nExpected:\n{}\nDiff:\n{}\n'.format(
            current_str,
            sample_str,
            '\n'.join(difflib.Differ().compare(current_str.splitlines(), sample_str.splitlines())),
        )
    )


def reset():
    active_test_files.clear()


def status():
    log.info('Sample files used:')
    if active_test_files:
        for filename in active_test_files:
            log.info(f'  {filename}')
    else:
        log.info('  None')


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


def _to_normalized_json(received_obj):
    return (
        json.dumps(
            received_obj, indent=4, sort_keys=True, cls=util.pretty.CustomJSONEncoder
        ).strip()
        + '\n'
    )


def _meld(left_str, filename):
    """Open the meld command with the contents of left_str in the left pane, and the contents of the
    named sample file in the right pane.
    - The function waits until the user closes the meld window, and then returns True if the
    contents are identical, or False if not.
    """
    with tempfile.NamedTemporaryFile(delete=True, suffix='.json') as tmp_file:
        tmp_file.write(left_str.encode('utf-8'))
        tmp_file.seek(0)
        subprocess.run(('meld', tmp_file.name, (TEST_FILES_PATH / filename).as_posix()))
        tmp_file.seek(0)
        return tmp_file.read() == (TEST_FILES_PATH / filename).read_bytes()


def _clobber_edi_ids(o):
    """Recursively clobber EDI IDs in the given dict or list, replacing them with a fixed string.
    This is useful for comparing JSON objects that contain EDI IDs that may vary between test runs.
    """
    if isinstance(o, str):
        return re.sub(r'^EDI-[a-f0-9]{40}$', '[CLOBBERED-EDI-ID]', o)
    elif isinstance(o, dict):
        for k, v in list(o.items()):
            o[k] = _clobber_edi_ids(v)
    elif isinstance(o, list):
        for i, item in enumerate(list(o)):
            o[i] = _clobber_edi_ids(item)
    return o
