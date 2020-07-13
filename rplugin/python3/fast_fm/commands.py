from asyncio import get_running_loop
from os.path import basename, dirname, exists, join, relpath
from typing import Callable, Iterator, Optional

# from .git import status
from .fs import ancestors, copy, cut, is_parent, new, remove, rename, unify
from .keymap import keymap
from .nvim import (
    Buffer,
    HoldPosition,
    HoldWindowPosition,
    Nvim2,
    Window,
    find_buffer,
    print,
)
from .state import forward, index, is_dir
from .types import Mode, Node, Settings, State
from .wm import is_fm_buffer, kill_buffers, show_file, toggle_shown, update_buffers


async def _index(nvim: Nvim2, state: State) -> Optional[Node]:
    window: Window = await nvim.api.get_current_win()
    row, _ = await nvim.api.win_get_cursor(window)
    row = row - 1
    return index(state, row)


def _indices(nvim: Nvim2, state: State, is_visual: bool) -> Iterator[Node]:
    if is_visual:
        buffer: Buffer = nvim.api.get_current_buf()
        r1, _ = nvim.api.buf_get_mark(buffer, "<")
        r2, _ = nvim.api.buf_get_mark(buffer, ">")
        for row in range(r1 - 1, r2):
            node = index(state, row)
            if node:
                yield node
    else:
        window: Window = nvim.api.get_current_win()
        row, _ = nvim.api.win_get_cursor(window)
        row = row - 1
        node = index(state, row)
        if node:
            yield node


async def _redraw(nvim: Nvim2, state: State) -> None:
    async with HoldPosition(nvim):
        await update_buffers(nvim, lines=state.rendered)


def _display_path(path: str, state: State) -> str:
    raw = relpath(path, start=state.root.path)
    return raw.replace("\n", r"\n")


async def a_on_filetype(
    nvim: Nvim2, state: State, settings: Settings, buf: int
) -> None:
    buffer = find_buffer(nvim, buf)
    if buffer:
        keymap(nvim, buffer=buffer, settings=settings)


async def a_on_bufenter(
    nvim: Nvim2, state: State, settings: Settings, buf: int
) -> State:
    buffer = find_buffer(nvim, buf)
    if buffer and is_fm_buffer(nvim, buffer=buffer):
        return state
    else:
        return state


async def a_on_focus(nvim: Nvim2, state: State, settings: Settings) -> State:
    return state


async def c_open(nvim: Nvim2, state: State, settings: Settings) -> None:
    await toggle_shown(nvim, settings=settings)
    await _redraw(nvim, state=state)


async def c_primary(nvim: Nvim2, state: State, settings: Settings) -> State:
    node = _index(nvim, state=state)
    if node:
        if Mode.FOLDER in node.mode:
            paths = {node.path}
            index = state.index ^ paths
            new_state = forward(state, settings=settings, index=index, paths=paths)
            _redraw(nvim, state=new_state)
            return new_state
        else:
            show_file(nvim, settings=settings, file=node.path)
            return state
    else:
        return state


async def c_secondary(nvim: Nvim2, state: State, settings: Settings) -> State:
    with HoldWindowPosition(nvim):
        return c_primary(nvim, state=state, settings=settings)


async def c_collapse(nvim: Nvim2, state: State, settings: Settings) -> State:
    node = _index(nvim, state=state)
    if node and Mode.FOLDER in node.mode:
        paths = {i for i in state.index if is_parent(parent=node.path, child=i)}
        index = state.index - paths
        new_state = forward(state, settings=settings, index=index, paths=paths)
        _redraw(nvim, state=new_state)
        return new_state
    else:
        return state


async def c_refresh(nvim: Nvim2, state: State, settings: Settings) -> State:
    paths = {state.root.path}
    new_state = forward(state, settings=settings, paths=paths)
    _redraw(nvim, state=new_state)
    return new_state


async def c_hidden(nvim: Nvim2, state: State, settings: Settings) -> State:
    new_state = forward(state, settings=settings, show_hidden=not state.show_hidden)
    _redraw(nvim, state=new_state)
    return new_state


async def c_follow(nvim: Nvim2, state: State, settings: Settings) -> State:
    new_state = forward(state, settings=settings, follow=not state.follow)
    return new_state


async def c_copy_name(nvim: Nvim2, state: State, settings: Settings) -> None:
    node = _index(nvim, state=state)
    if node:
        path = node.path
        nvim.funcs.setreg("+", path)
        nvim.funcs.setreg("*", path)
        print(nvim, f"📎 {path}")


async def c_new(nvim: Nvim2, state: State, settings: Settings) -> State:
    node = _index(nvim, state=state)
    if node:
        parent = node.path if is_dir(node) else dirname(node.path)
        child = nvim.funcs.input("✏️  :")
        name = join(parent, child)
        if exists(name):
            msg = f"⚠️  Exists: {name}"
            print(nvim, msg, error=True)
            return state
        else:
            try:
                new(name)
            finally:
                index = state.index | {*ancestors(name)}
                new_state = forward(
                    state, settings=settings, index=index, paths={parent}
                )
                _redraw(nvim, state=new_state)
                return new_state
    else:
        return state


async def c_rename(nvim: Nvim2, state: State, settings: Settings) -> State:
    node = _index(nvim, state=state)
    if node:
        prev_name = node.path
        parent = state.root.path
        rel_path = relpath(prev_name, start=parent)
        child = nvim.funcs.input("✏️  :", rel_path)
        new_name = join(parent, child)
        new_parent = dirname(new_name)
        if exists(new_name):
            msg = f"⚠️  Exists: {new_name}"
            print(nvim, msg, error=True)
            return state
        else:
            try:
                rename(prev_name, new_name)
            finally:
                paths = {parent, new_parent, *ancestors(new_parent)}
                index = state.index | paths
                new_state = forward(state, settings=settings, index=index, paths=paths)
                _redraw(nvim, state=new_state)
                kill_buffers(nvim, paths=(prev_name,))
                return new_state
    else:
        return state


async def c_clear(nvim: Nvim2, state: State, settings: Settings) -> State:
    new_state = forward(state, settings=settings, selection=set())
    _redraw(nvim, state=new_state)
    return new_state


async def c_select(
    nvim: Nvim2, state: State, settings: Settings, is_visual: bool
) -> State:
    nodes = _indices(nvim, state=state, is_visual=is_visual)
    if is_visual:
        selection = state.selection ^ {n.path for n in nodes}
        new_state = forward(state, settings=settings, selection=selection)
        _redraw(nvim, state=new_state)
        return new_state
    else:
        node = next(nodes, None)
        if node:
            selection = state.selection ^ {node.path}
            new_state = forward(state, settings=settings, selection=selection)
            _redraw(nvim, state=new_state)
            return new_state
        else:
            return state


async def c_delete(nvim: Nvim2, state: State, settings: Settings) -> State:
    node = _index(nvim, state=state)
    selection = state.selection or ({node.path} if node else set())
    if selection:
        unified = tuple(unify(selection))
        display_paths = "\n".join(_display_path(path, state=state) for path in unified)
        ans = nvim.funcs.confirm(f"🗑  {display_paths}?", "&Yes\n&No\n", 2)
        if ans == 1:
            try:
                await remove(unified)
            finally:
                paths = {dirname(path) for path in unified}
                new_state = forward(state, settings=settings, paths=paths)
                _redraw(nvim, state=new_state)
                kill_buffers(nvim, paths=selection)
                return new_state
        else:
            return state
    else:
        return state


def _find_dest(src: str, node: Node) -> str:
    name = basename(src)
    parent = node.path if is_dir(node) else dirname(node.path)
    dst = join(parent, name)
    return dst


async def _operation(
    nvim: Nvim2,
    *,
    state: State,
    settings: Settings,
    name: str,
    action: Callable[[str, str], None],
) -> State:
    node = _index(nvim, state=state)
    selection = state.selection
    if selection and node:
        operations = {src: _find_dest(src, node) for src in selection}
        pre_existing = {s: d for s, d in operations.items() if exists(d)}
        if pre_existing:
            msg = ", ".join(
                f"{_display_path(s, state=state)} -> {_display_path(d, state=state)}"
                for s, d in pre_existing.items()
            )
            print(nvim, f"⚠️  -- {name}: path(s) already exist! :: {msg}", error=True)
            return state
        else:
            try:
                for src, dest in operations.items():
                    action(src, dest)
            finally:
                paths = {
                    *operations.values(),
                    *(dirname(src) for src in operations.keys()),
                }
                index = state.index | paths
                new_state = forward(state, settings=settings, index=index, paths=paths)
                _redraw(nvim, state=new_state)
                kill_buffers(nvim, paths=selection)
                return new_state
    else:
        print(nvim, "⚠️  -- {name}: nothing selected!", error=True)
        return state


async def c_cut(nvim: Nvim2, state: State, settings: Settings) -> State:
    return await _operation(
        nvim, state=state, settings=settings, name="Cut", action=cut
    )


async def c_copy(nvim: Nvim2, state: State, settings: Settings) -> State:
    return await _operation(
        nvim, state=state, settings=settings, name="Copy", action=copy
    )
