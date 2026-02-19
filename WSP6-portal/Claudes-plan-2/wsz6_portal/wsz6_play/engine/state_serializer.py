"""
wsz6_play/engine/state_serializer.py

Serialize / deserialize SZ_State subclass instances to/from
JSON-compatible dicts for:
  - WebSocket state broadcast to players
  - Checkpoint persistence to disk

Protocol (preferred):
    PFF State classes implement ``to_dict()`` / ``from_dict(cls, data)``.

Fallback (automatic):
    __dict__-based copy with basic JSON type coercion for simple states.
"""


def serialize_state(state) -> dict:
    """Convert an SZ_State instance to a JSON-compatible dict.

    If the state has a ``to_dict()`` method it is called; otherwise the
    ``__dict__`` is copied with basic type coercion.  The result always
    contains a ``'__class__'`` key with the class qualified name (for
    debugging; not used during deserialization).
    """
    if hasattr(state, 'to_dict') and callable(state.to_dict):
        d = state.to_dict()
    else:
        d = _fallback_serialize(state)
    d['__class__'] = type(state).__qualname__
    return d


def deserialize_state(data: dict, state_class):
    """Reconstruct an SZ_State from a serialized dict.

    Args:
        data:        dict produced by ``serialize_state()``.
        state_class: the State class (e.g. ``TTT_State``).  Must already be
                     importable from the PFF module loaded for this session.

    If ``state_class`` has a ``from_dict(cls, data)`` class method it is
    used; otherwise ``__dict__`` is restored directly.
    """
    cleaned = {k: v for k, v in data.items() if k != '__class__'}
    if hasattr(state_class, 'from_dict') and callable(state_class.from_dict):
        return state_class.from_dict(cleaned)
    obj = object.__new__(state_class)
    obj.__dict__.update(cleaned)
    return obj


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fallback_serialize(state) -> dict:
    result = {}
    for key, val in vars(state).items():
        result[key] = _coerce(val)
    return result


def _coerce(val):
    """Recursively coerce a value to a JSON-serializable type."""
    if isinstance(val, (bool, int, float, str, type(None))):
        return val
    if isinstance(val, (list, tuple)):
        return [_coerce(v) for v in val]
    if isinstance(val, dict):
        return {str(k): _coerce(v) for k, v in val.items()}
    # Last resort: convert to string.
    return str(val)
