"""Accent color, and where it is shown."""

from .base import Context, Setting
from .theme import PERSONALIZE

DWM = r"Software\Microsoft\Windows\DWM"
ACCENT = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"
DESKTOP = r"Control Panel\Desktop"


class Accent(Setting):
    name = "accent"
    label = "Accent color"
    values = (
        (DESKTOP, "AutoColorization"),
        (ACCENT, "AccentColorMenu"),
        (ACCENT, "StartColorMenu"),
        (ACCENT, "AccentPalette"),
        (DWM, "AccentColor"),
        (DWM, "ColorizationColor"),
        (DWM, "ColorizationAfterglow"),
        # Accent color on title bars and window borders.
        (DWM, "ColorPrevalence"),
        # Accent color on Start and the taskbar.
        (PERSONALIZE, "ColorPrevalence"),
    )

    def after_apply(self, ctx: Context) -> None:
        ctx.system.broadcast_setting_change("ImmersiveColorSet")
