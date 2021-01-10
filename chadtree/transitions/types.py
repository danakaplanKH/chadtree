from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from ..state.types import State


class ClickType(Enum):
    primary = auto()
    secondary = auto()
    tertiary = auto()
    v_split = auto()
    h_split = auto()


@dataclass(frozen=True)
class Stage:
    state: State
    focus: Optional[str] = None


class SysError(Exception):
    ...
