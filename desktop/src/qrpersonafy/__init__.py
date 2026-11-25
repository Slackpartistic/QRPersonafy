"""QRestoa: save and restore your desktop look on Windows and Linux.

The Python package keeps its first name, qrpersonafy, so plug-ins and scripts keep working.
"""

__version__ = "1.2.0"

APP_NAME = "QRestoa"
# The app's own folder in (Local)AppData on Windows and ~/.local/share on Linux. Versions before
# the rename used "QRPersonafy"; backups there still count, so Undo keeps working after an update.
APP_FOLDER = APP_NAME
OLD_APP_FOLDER = "QRPersonafy"
