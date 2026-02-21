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

Refactoring note (Games_File_System_Refactoring.md):
    load_formulation() adds settings.SOLUZION_LIB_DIR (Textual_SZ6/) to
    sys.path so PFFs can `from soluzion6_02 import ...` without a per-game
    copy of soluzion6_02.py.  load_vis_module() auto-discovers *_WSZ6_VIS.py
    files so PFFs no longer need to import the vis module explicitly.
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

    (with a fallback that scans the directory for any *.py file that is not
    a vis module or __init__.py).

    Before adding the game directory to sys.path, this function inserts
    settings.SOLUZION_LIB_DIR (pointing to Textual_SZ6/) so that PFFs can
    ``from soluzion6_02 import ...`` without a per-game copy of that file.

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

    # Add the shared SOLUZION6 base library directory so PFFs can import
    # soluzion6_02 without a per-game copy.  Must be done before sys.path
    # already contains game_dir so that a stale game-dir copy (if any) is
    # overshadowed by the canonical single-source version.
    _ensure_shared_lib_on_path()

    # Ensure the game directory is on sys.path so the PFF can import
    # any remaining game-local helper modules.
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


def load_vis_module(game_dir: str):
    """Auto-discover and load a vis module from the game directory.

    Scans ``game_dir`` for files matching ``*_WSZ6_VIS.py``.  If exactly one
    is found, it is imported and returned as a module object.

    - Returns None if no vis file exists (game has no visualization).
    - Logs a warning and returns None if multiple vis files are found.
    - Logs a warning and returns None if the vis file fails to import.

    The returned module is loaded into sys.modules under a unique name so
    multiple concurrent sessions each get their own independent module state.

    Callers should attach the result to the formulation only when
    ``formulation.vis_module`` is not already set by the PFF itself, so that
    explicit PFF-level vis assignments take precedence.
    """
    try:
        vis_files = [
            f for f in os.listdir(game_dir)
            if f.endswith('_WSZ6_VIS.py')
        ]
    except FileNotFoundError:
        return None

    if not vis_files:
        return None
    if len(vis_files) > 1:
        logger.warning(
            "Multiple _WSZ6_VIS.py files found in %s: %s — skipping auto-discovery.",
            game_dir, vis_files,
        )
        return None

    vis_path    = os.path.join(game_dir, vis_files[0])
    unique_name = f"_vis_{uuid.uuid4().hex}"
    try:
        spec = importlib.util.spec_from_file_location(unique_name, vis_path)
        if spec is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module
        spec.loader.exec_module(module)
        logger.debug("Auto-loaded vis module: %s → %s", vis_files[0], unique_name)
        return module
    except Exception as exc:
        sys.modules.pop(unique_name, None)
        logger.warning("Failed to load vis module %s: %s", vis_path, exc)
        return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ensure_shared_lib_on_path() -> None:
    """Insert settings.SOLUZION_LIB_DIR into sys.path if not already present."""
    try:
        from django.conf import settings
        shared_lib = getattr(settings, 'SOLUZION_LIB_DIR', None)
    except Exception:
        shared_lib = None

    if shared_lib and os.path.isdir(shared_lib) and shared_lib not in sys.path:
        sys.path.insert(0, shared_lib)


def _find_pff_file(game_dir: str, game_slug: str) -> str:
    """Return the path to the game's main PFF Python file.

    Search order:
    1. ``<game_dir>/<game_slug with hyphens replaced by underscores>.py``
    2. ``<game_dir>/<game_slug>.py``
    3. Any single ``*.py`` file in ``game_dir`` that is not a vis module
       (``*_WSZ6_VIS.py``) and not ``__init__.py``.
    """
    slug_underscore = game_slug.replace('-', '_')
    candidates = [
        os.path.join(game_dir, f"{slug_underscore}.py"),
        os.path.join(game_dir, f"{game_slug}.py"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Fallback: scan directory, excluding vis modules and __init__.py.
    try:
        py_files = sorted(
            f for f in os.listdir(game_dir)
            if f.endswith('.py')
            and f != '__init__.py'
            and not f.endswith('_WSZ6_VIS.py')
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
