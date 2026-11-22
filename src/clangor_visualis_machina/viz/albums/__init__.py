"""Dispatch album painters without masking broken known-album implementations.

Stage calls build_scene with immutable movement metadata. Only unknown families use the
self-contained generic composition; import and factory errors in known albums propagate.
"""

from importlib import import_module

from ..scene import Movement, Scene

_FAMILIES = frozenset(
    ("coupon", "aquatic", "forest", "pocket", "rooms", "undertow", "haunt", "dusk")
)


def build_scene(movement: Movement) -> Scene:
    """Construct the album's painter or the unknown-family fallback.

    Args:
        movement: Composition metadata, including the registry family key.

    Returns:
        A new scene, not yet resized or rendered.

    Raises:
        ImportError: A registered album implementation cannot be imported.
        Exception: Album factory failures propagate rather than hiding broken art.
    """
    family = movement.family if movement.family in _FAMILIES else "generic"
    module = import_module(f"{__name__}.{family}")
    return module.build_scene(movement)
