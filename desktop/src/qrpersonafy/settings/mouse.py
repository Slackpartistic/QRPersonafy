"""Pointer speed and acceleration, button swap, double-click, scrolling and cursor scheme."""

from ..system import (
    SPI_SETCURSORS,
    SPI_SETDOUBLECLICKTIME,
    SPI_SETMOUSE,
    SPI_SETMOUSEBUTTONSWAP,
    SPI_SETMOUSESPEED,
    SPI_SETWHEELSCROLLLINES,
)
from .base import Context, Setting, dword

MOUSE = r"Control Panel\Mouse"
DESKTOP = r"Control Panel\Desktop"
CURSORS = r"Control Panel\Cursors"


class Mouse(Setting):
    name = "mouse"
    label = "Mouse"
    values = (
        (MOUSE, "MouseSensitivity"),
        (MOUSE, "MouseSpeed"),
        (MOUSE, "MouseThreshold1"),
        (MOUSE, "MouseThreshold2"),
        (MOUSE, "SwapMouseButtons"),
        (MOUSE, "DoubleClickSpeed"),
        (DESKTOP, "WheelScrollLines"),
        (DESKTOP, "WheelScrollChars"),
    )
    whole_keys = (CURSORS,)

    def after_apply(self, ctx: Context) -> None:
        calls = []
        if (speed := dword(ctx, MOUSE, "MouseSensitivity")) is not None:
            calls.append((SPI_SETMOUSESPEED, 0, speed))
        acceleration = [dword(ctx, MOUSE, n) for n in ("MouseThreshold1", "MouseThreshold2", "MouseSpeed")]
        if None not in acceleration:
            calls.append((SPI_SETMOUSE, 0, acceleration))
        if (swap := dword(ctx, MOUSE, "SwapMouseButtons")) is not None:
            calls.append((SPI_SETMOUSEBUTTONSWAP, swap, None))
        if (double_click := dword(ctx, MOUSE, "DoubleClickSpeed")) is not None:
            calls.append((SPI_SETDOUBLECLICKTIME, double_click, None))
        if (lines := dword(ctx, DESKTOP, "WheelScrollLines")) is not None:
            calls.append((SPI_SETWHEELSCROLLLINES, lines, None))
        calls.append((SPI_SETCURSORS, 0, None))
        for action, ui_param, pv_param in calls:
            try:
                ctx.system.spi(action, ui_param, pv_param)
            except OSError as error:
                ctx.warn(f"Mouse: {error}")
