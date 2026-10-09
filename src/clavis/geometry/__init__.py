"""Staff geometry and layout."""

from .config import GeometryConfig, load_config
from .staff import Detection, StaffCandidate, detect_staves, estimate_interline
from .strip import extract_strip, processed_to_strip, remove_staff_lines, strip_to_processed

__all__ = [
    "GeometryConfig",
    "load_config",
    "Detection",
    "StaffCandidate",
    "detect_staves",
    "estimate_interline",
    "extract_strip",
    "processed_to_strip",
    "remove_staff_lines",
    "strip_to_processed",
]
