"""
wsz6_play/engine/pff_loader.py

Dynamically loads a SOLUZION6 Problem Formulation File (PFF) module.

Each call registers the module under a unique name so that two concurrent
sessions using the same game never share module-level state (e.g. class
variables, role assignments, formulation instances).

Phase-2 architectural note:
    load_formulation() is called twice per play-through:
      1. During launch_session (HTTP, sync) → to extract roles_spec.
      2. When the lobby starts the game (WS, via asyncio.to_thread) → for
         the actual GameRunner instance that owns game state.
    Each call gets its own module instance.
"""

import importlib.util
import logging
import os
import sys
import uuid

logger = logging.getLogger(__name__)


class PFFLoadError(Exception):
    """Raised when a PFF cannot be found, loaded, or validated."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_formulation(game_slug: str, games_repo_root: str):
    """Load and return the SZ_Formulation instance from the game's PFF.

    Searches for the PFF in::

        <games_repo_root>/<game_slug>/<game_slug>.py

    (with a fallback that scans the directory for any *.py file).

    The module is inserted into ``sys.modules`` under a unique name
    ``_pff_<slug>_<uuid32hex>`` so it is never confused with any other
    session's copy of the same game.

    Returns:
        The SZ_Formulation instance found in the module.

    Raises:
        PFFLoadError: on any failure (file not found, import error,
                      no formulation instance found).
    """
    game_dir = os.path.join(games_repo_root, game_slug)
    pff_path = _find_pff_file(game_dir, game_slug)

    # Ensure the game directory is on sys.path so the PFF can import
    # local helper modules (e.g. soluzion6_02.py bundled with the game).
    if game_dir not in sys.path:
        sys.path.insert(0, game_dir)

    unique_name = f"_pff_{game_slug.replace('-', '_')}_{uuid.uuid4().hex}"
    try:
        spec = importlib.util.spec_from_file_location(unique_name, pff_path)
        if spec is None:
            raise PFFLoadError(f"Cannot create module spec from: {pff_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        spec.loader.exec_module(module)
    except PFFLoadError:
        raise
    except Exception as exc:
        sys.modules.pop(unique_name, None)
        raise PFFLoadError(f"Error loading PFF '{pff_path}': {exc}") from exc

    formulation = _find_formulation(module)
    if formulation is None:
        sys.modules.pop(unique_name, None)
        raise PFFLoadError(
            f"No SZ_Formulation instance found in '{pff_path}'. "
            "The PFF must instantiate a subclass of SZ_Formulation at module level."
        )

    # Tag so callers can unload later if desired.
    formulation._pff_module_name = unique_name
    logger.debug("Loaded PFF: %s → %s (%s)", game_slug, formulation, unique_name)
    return formulation


def unload_formulation(formulation) -> None:
    """Remove the formulation's module from sys.modules (optional cleanup)."""
    name = getattr(formulation, '_pff_module_name', None)
    if name:
        sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _find_pff_file(game_dir: str, game_slug: str) -> str:
    """Return the path to the game's main PFF Python file.

    Search order:
    1. ``<game_dir>/<game_slug with hyphens replaced by underscores>.py``
    2. ``<game_dir>/<game_slug>.py``
    3. Any single ``*.py`` file in ``game_dir`` (excluding ``__init__.py``).
    """
    slug_underscore = game_slug.replace('-', '_')
    candidates = [
        os.path.join(game_dir, f"{slug_underscore}.py"),
        os.path.join(game_dir, f"{game_slug}.py"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Fallback: scan directory.
    try:
        py_files = sorted(
            f for f in os.listdir(game_dir)
            if f.endswith('.py') and f != '__init__.py'
        )
    except FileNotFoundError:
        raise PFFLoadError(f"Game directory not found: {game_dir!r}")
    if not py_files:
        raise PFFLoadError(f"No .py files found in game directory: {game_dir!r}")
    return os.path.join(game_dir, py_files[0])


def _find_formulation(module):
    """Return the first SZ_Formulation-like instance found in the module.

    Uses duck-typing: an object qualifies if it has ``metadata``,
    ``operators``, and a callable ``initialize_problem`` attribute, and is
    *not* a class itself.
    """
    for attr_name in dir(module):
        try:
            obj = getattr(module, attr_name)
        except Exception:
            continue
        if (
            obj is not None
            and not isinstance(obj, type)
            and hasattr(obj, 'metadata')
            and hasattr(obj, 'operators')
            and callable(getattr(obj, 'initialize_problem', None))
        ):
            return obj
    return None
