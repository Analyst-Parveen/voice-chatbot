"""Domain enumerations.

Stored as short strings (cross-dialect friendly) but exposed as typed Python
enums for validation at the application boundary.
"""

from __future__ import annotations

from enum import Enum


class Channel(str, Enum):
    VOICE = "voice"
    TEXT = "text"


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class InputType(str, Enum):
    VOICE = "voice"
    TEXT = "text"


class Rating(str, Enum):
    UP = "up"
    DOWN = "down"
