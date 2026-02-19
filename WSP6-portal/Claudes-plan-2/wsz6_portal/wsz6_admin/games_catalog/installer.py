"""
wsz6_admin/games_catalog/installer.py

Utilities for validating and extracting a game ZIP archive,
then sandbox-importing the PFF to extract metadata.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings


# ---------------------------------------------------------------------------
# ZIP validation and extraction
# ---------------------------------------------------------------------------

class InstallError(Exception):
    """Raised when installation cannot proceed."""


def validate_and_extract(zip_fileobj, game_slug: str) -> Path:
    """
    Validate the ZIP and extract it to GAMES_REPO_ROOT/<game_slug>/.

    Returns the path to the extracted game directory.
    Raises InstallError on any validation failure.
    """
    try:
        zf = zipfile.ZipFile(zip_fileobj)
    except zipfile.BadZipFile:
        raise InstallError('The uploaded file is not a valid ZIP archive.')

    names = zf.namelist()
    _check_for_path_traversal(names)
    _check_contains_python(names)

    dest = Path(settings.GAMES_REPO_ROOT) / game_slug
    dest.mkdir(parents=True, exist_ok=True)

    # Strip a single top-level directory if all entries share one.
    prefix = _common_prefix(names)
    for member in zf.infolist():
        target_name = member.filename
        if prefix and target_name.startswith(prefix):
            target_name = target_name[len(prefix):]
        if not target_name:  # was the top-level directory itself
            continue
        target_path = dest / target_name
        if member.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(zf.read(member.filename))

    return dest


def _check_for_path_traversal(names):
    for name in names:
        p = Path(name)
        if '..' in p.parts:
            raise InstallError(
                f'ZIP contains a path traversal entry: "{name}". Aborting.'
            )


def _check_contains_python(names):
    if not any(n.endswith('.py') for n in names):
        raise InstallError('ZIP must contain at least one Python (.py) file.')


def _common_prefix(names):
    """Return a common directory prefix if all entries share one, else ''."""
    if not names:
        return ''
    parts = [n.split('/')[0] for n in names]
    first = parts[0]
    if all(p == first for p in parts) and not names[0].startswith(first + '.'):
        return first + '/'
    return ''


# ---------------------------------------------------------------------------
# PFF sandbox validation
# ---------------------------------------------------------------------------

_VALIDATOR_SCRIPT = """
import sys, json, importlib.util

module_path = sys.argv[1]
spec   = importlib.util.spec_from_file_location('_pff_validate', module_path)
module = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(module)
except Exception as e:
    print(json.dumps({'error': str(e)}))
    sys.exit(1)

# Find first SZ_Formulation-like object (duck typing: has .metadata).
result = {}
for attr_name in dir(module):
    obj = getattr(module, attr_name)
    meta = getattr(obj, 'metadata', None)
    if meta is not None and hasattr(meta, 'name'):
        result['name']    = getattr(meta, 'name',             attr_name)
        result['version'] = getattr(meta, 'problem_version',  getattr(meta, 'soluzion_version', '?'))
        result['desc']    = getattr(meta, 'brief_desc',       '')
        result['authors'] = getattr(meta, 'authors',          [])
        roles_spec = getattr(obj, 'roles_spec', None)
        if roles_spec is not None:
            result['min_players'] = getattr(roles_spec, 'min_players_to_start', 1)
            result['max_players'] = getattr(roles_spec, 'max_players', 10)
        break

if not result:
    result['error'] = 'No SZ_Formulation instance with .metadata found in the module.'

print(json.dumps(result))
"""


def validate_pff(game_dir: Path) -> dict:
    """
    Run the PFF file(s) in game_dir through a sandboxed subprocess.

    Returns a dict with keys: name, version, desc, authors,
    min_players, max_players.
    Raises InstallError if validation fails.
    """
    py_files = sorted(game_dir.glob('*.py'))
    if not py_files:
        raise InstallError('No Python files found in the extracted game directory.')

    # Write the validator script to a temp file.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py',
                                     delete=False, prefix='pff_validator_') as tf:
        tf.write(_VALIDATOR_SCRIPT)
        validator_path = tf.name

    best_result = None
    last_error  = 'No suitable PFF found.'

    try:
        for py_file in py_files:
            # Add game_dir to sys.path so the PFF can import local helpers.
            env = os.environ.copy()
            env['PYTHONPATH'] = str(game_dir) + os.pathsep + env.get('PYTHONPATH', '')

            try:
                proc = subprocess.run(
                    [sys.executable, validator_path, str(py_file)],
                    capture_output=True, text=True, timeout=10, env=env,
                )
                if proc.stdout.strip():
                    data = json.loads(proc.stdout.strip())
                    if 'error' not in data:
                        best_result = data
                        break
                    else:
                        last_error = data['error']
            except (subprocess.TimeoutExpired, json.JSONDecodeError):
                last_error = f'Timeout or bad output from {py_file.name}.'
    finally:
        os.unlink(validator_path)

    if best_result is None:
        raise InstallError(f'PFF validation failed: {last_error}')

    return best_result
