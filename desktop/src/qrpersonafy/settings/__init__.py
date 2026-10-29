"""All the setting groups QRPersonafy can save and restore, in the order they are applied."""

from .accent import Accent
from .base import Context, Setting
from .keyboard import Keyboard
from .mouse import Mouse
from .start import Start
from .taskbar import Taskbar
from .theme import Theme
from .wallpaper import Wallpaper

ALL: tuple[Setting, ...] = (Wallpaper(), Theme(), Accent(), Taskbar(), Start(), Mouse(), Keyboard())
BY_NAME = {setting.name: setting for setting in ALL}

__all__ = ["ALL", "BY_NAME", "Context", "Setting"]
