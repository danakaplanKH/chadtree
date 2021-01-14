from typing import Sequence

from pynvim import Nvim
from pynvim_pp.api import buf_set_lines, buf_set_option, create_buf
from pynvim_pp.float_win import open_float_win
from std2.argparse import ArgParser

from ..consts import CONFIGURATION_MD, KEYBIND_MD, README_MD
from ..registry import rpc
from ..settings.types import Settings
from ..state.types import State


@rpc(blocking=False)
def _help(nvim: Nvim, state: State, settings: Settings, args: Sequence[str]) -> None:
    """
    Open help doc
    """

    lines = README_MD.read_text().splitlines()
    buf = create_buf(nvim, listed=False, scratch=True, wipe=True, nofile=True)
    buf_set_lines(nvim, buf=buf, lo=0, hi=-1, lines=lines)
    buf_set_option(nvim, buf=buf, key="modifiable", val=False)
    buf_set_option(nvim, buf=buf, key="filetype", val="markdown")
    open_float_win(nvim, margin=0, relsize=0.95, buf=buf)
