"""Services package for STRIX."""

from .slice_registry import slice_registry, TOTAL_BANDWIDTH_CAPACITY
from .intent_parser import intent_parser
from .conflict_detector import conflict_detector
from .sdn_controller import sdn_controller

__all__ = [
    "slice_registry",
    "TOTAL_BANDWIDTH_CAPACITY",
    "intent_parser",
    "conflict_detector",
    "sdn_controller",
]
