import subprocess
import tempfile
import json
import pathlib

HERE_PATH = pathlib.Path(__file__).parent.resolve()
TEST_FILES_PATH = HERE_PATH / 'tests' / 'test_files'


def assert_equal(got_str, filename):
    """Assert that the string is identical to the contents of the sample file"""
    expected_str = _read_file(filename)
    if got_str != expected_str:
        print('Got:')
        print(got_str)
        print('Expected:')
        print(expected_str)
        # assert False
        meld(got_str, filename)
        # assert got_str == expected_str


def assert_equal_json(got_json_str, filename):
    """Assert that the JSON string is semantically identical to the contents of the sample file"""
    norm_json_str = _normalize_json(got_json_str)
    expected_json_str = _read_file(filename)
    # assert norm_json_str == expected_json_str
    if norm_json_str != expected_json_str:
        print('Got JSON:')
        print(norm_json_str)
        print('Expected JSON:')
        print(expected_json_str)
        # assert False
        meld(norm_json_str, filename)
        # assert norm_json_str == expected_json_str


def _read_file(filename):
    file_path = TEST_FILES_PATH / filename
    if not file_path.exists():
        file_path.touch()
    return file_path.read_text()


def _normalize_json(json_str):
    return json.dumps(json.loads(json_str), indent=4, sort_keys=True).strip() + '\n'


def meld(left_str, filename):
    """Open the meld command with left and right files"""
    with tempfile.NamedTemporaryFile(delete=True, suffix='.json') as tmp_file:
        tmp_file.write(left_str.encode('utf-8'))
        tmp_file.seek(0)
        subprocess.run(
            ('meld', tmp_file.name, (TEST_FILES_PATH / filename).as_posix()),
        )
