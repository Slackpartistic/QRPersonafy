"""Desktop wallpaper image and how it is fitted to the screen."""

from __future__ import annotations

from pathlib import Path

from ..system import SPI_SETDESKWALLPAPER
from .base import Context, Setting, pack_file, unpack_file

DESKTOP = r"Control Panel\Desktop"

_SIGNATURES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"BM": ".bmp",
}


def image_extension(data: bytes) -> str:
    for signature, extension in _SIGNATURES.items():
        if data.startswith(signature):
            return extension
    return ".jpg"


class Wallpaper(Setting):
    name = "wallpaper"
    label = "Wallpaper"
    values = (
        (DESKTOP, "WallpaperStyle"),
        (DESKTOP, "TileWallpaper"),
    )

    def export_extra(self, ctx: Context, section: dict) -> None:
        # The path in the registry may point at a file that has since moved, so fall back to
        # the copy Windows keeps of whatever is on screen.
        candidates = []
        current = ctx.registry.get(DESKTOP, "Wallpaper")
        if current is not None and isinstance(current.data, str) and current.data:
            candidates.append(Path(current.data))
        candidates.append(ctx.system.appdata / "Microsoft" / "Windows" / "Themes" / "TranscodedWallpaper")
        for path in candidates:
            if path.is_file():
                data = path.read_bytes()
                section["files"] = {"image": pack_file("wallpaper" + image_extension(data), data)}
                return
        ctx.warn("Wallpaper: no wallpaper image found, saving fit settings only")

    def apply_extra(self, ctx: Context, section: dict) -> None:
        entry = section.get("files", {}).get("image")
        if entry is None:
            return
        _, data = unpack_file(entry)
        target = ctx.system.appdata / "QRPersonafy" / ("wallpaper" + image_extension(data))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        try:
            ctx.system.spi(SPI_SETDESKWALLPAPER, 0, str(target))
        except OSError as error:
            ctx.warn(f"Wallpaper: could not set the wallpaper: {error}")
