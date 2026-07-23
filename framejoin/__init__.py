"""FrameJoin Studio package."""

__version__ = "0.25"

# Keep continuous image-sequence exports zero-based by default even when older
# project dictionaries omit the newer numbering fields. The generated dataclass
# initializer stores defaults positionally, so update the two relevant entries
# once when the package is imported.
from .models import JoinSettings


def _apply_sequence_numbering_defaults() -> None:
    defaults = list(JoinSettings.__init__.__defaults__ or ())
    field_names = list(JoinSettings.__dataclass_fields__)
    if len(defaults) != len(field_names):
        return
    defaults[field_names.index("sequence_frame_start")] = 0
    defaults[field_names.index("sequence_frame_digits")] = 6
    JoinSettings.__init__.__defaults__ = tuple(defaults)


_apply_sequence_numbering_defaults()
del _apply_sequence_numbering_defaults
