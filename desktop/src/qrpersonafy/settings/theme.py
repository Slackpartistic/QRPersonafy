"""Light/dark mode and transparency."""

from .base import Context, Setting

PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


class Theme(Setting):
    name = "theme"
    label = "Light/dark mode"
    values = (
        (PERSONALIZE, "AppsUseLightTheme"),
        (PERSONALIZE, "SystemUsesLightTheme"),
        (PERSONALIZE, "EnableTransparency"),
    )

    def after_apply(self, ctx: Context) -> None:
        ctx.system.broadcast_setting_change("ImmersiveColorSet")
