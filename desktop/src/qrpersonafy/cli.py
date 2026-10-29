"""Command line: qrpersonafy export | apply | send | receive | show."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .profile import apply_profile, check_profile, export_profile, load_profile, save_profile
from .profile import back_up as save_backup
from .settings import ALL, BY_NAME, Context

NAMES = ", ".join(s.name for s in ALL)


def parse_only(value: str | None) -> set[str]:
    if not value:
        return set(BY_NAME)
    names = {n.strip().lower() for n in value.split(",") if n.strip()}
    unknown = names - set(BY_NAME)
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown setting(s): {', '.join(sorted(unknown))}. Choose from: {NAMES}")
    return names


def windows_context() -> Context:
    if sys.platform != "win32":
        raise SystemExit("This command only works on Windows.")
    from .registry import WindowsRegistry
    from .system import WindowsSystem

    return Context(WindowsRegistry(), WindowsSystem())


def print_warnings(ctx: Context) -> None:
    for warning in ctx.warnings:
        print(f"warning: {warning}", file=sys.stderr)


def cmd_export(args: argparse.Namespace) -> int:
    ctx = windows_context()
    profile = export_profile(ctx, args.only)
    save_profile(profile, args.output)
    print(f"Saved {', '.join(profile['settings'])} to {args.output}")
    print_warnings(ctx)
    return 0


def back_up(ctx: Context, names: set[str]) -> None:
    print(f"Backed up current settings to {save_backup(ctx, names)}")


def cmd_apply(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    if args.dry_run:
        return show(profile, args.only)
    ctx = windows_context()
    if not args.no_backup:
        back_up(ctx, args.only)
    applied = apply_profile(ctx, profile, args.only)
    print(f"Applied {', '.join(applied) or 'nothing'}")
    print_warnings(ctx)
    return 0


def show(profile: dict, names: set[str]) -> int:
    print(f"Profile from {profile.get('created', '?')}, Windows build {profile.get('windows_build', '?')}")
    for setting in ALL:
        section = profile["settings"].get(setting.name)
        if setting.name not in names or section is None:
            continue
        print(f"\n[{setting.name}] {setting.label}")
        try:
            lines = setting.describe(section)
        except (ValueError, TypeError, AttributeError) as error:
            lines = [f"malformed: {error}"]
        for line in lines:
            print(f"  {line}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    return show(load_profile(args.profile), args.only)


def show_qr(uri: str) -> None:
    import qrcode

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
    qr.add_data(uri)
    try:
        qr.print_ascii(invert=True)
    except UnicodeEncodeError:
        # The console can't draw block characters (e.g. output redirected), so show an image instead.
        import os
        import tempfile

        import qrcode.image.svg

        path = Path(tempfile.gettempdir()) / "qrpersonafy-pair.svg"
        qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(str(path))
        print(f"QR code saved to {path}")
        if sys.platform == "win32":
            os.startfile(path)


def serve_session(session) -> bool:
    show_qr(session.uri())
    print("Scan this with the QRPersonafy app. Waiting up to 10 minutes, Ctrl+C to cancel.")
    try:
        return session.serve()
    except KeyboardInterrupt:
        print("Cancelled.")
        return False


def cmd_send(args: argparse.Namespace) -> int:
    from .pairing import PairingSession

    ctx = windows_context()
    profile = export_profile(ctx, args.only)
    print_warnings(ctx)
    session = PairingSession("send", profile=profile, port=args.port)
    if not serve_session(session):
        print("Nothing was sent.")
        return 1
    print(f"Sent {', '.join(profile['settings'])} to your phone.")
    return 0


def cmd_receive(args: argparse.Namespace) -> int:
    from .pairing import PairingSession

    ctx = windows_context()

    def on_receive(profile: dict) -> tuple[int, dict]:
        try:
            check_profile(profile)
        except ValueError as error:
            return 400, {"error": str(error)}
        print()
        show(profile, args.only)
        if not args.yes and input("\nApply these settings to this PC? [y/N] ").strip().lower() not in ("y", "yes"):
            return 403, {"error": "declined on the PC"}
        if not args.no_backup:
            back_up(ctx, args.only)
        applied = apply_profile(ctx, profile, args.only)
        print(f"Applied {', '.join(applied) or 'nothing'}")
        print_warnings(ctx)
        return 200, {"applied": applied, "warnings": ctx.warnings}

    session = PairingSession("receive", on_receive=on_receive, port=args.port)
    if not serve_session(session):
        print("Nothing was received.")
        return 1
    return 0 if session.result and "applied" in session.result else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qrpersonafy", description="Save and restore Windows personalization.")
    commands = parser.add_subparsers(dest="command", required=True)
    only_help = f"comma-separated settings to include (default: all of {NAMES})"

    export = commands.add_parser("export", help="save this PC's settings to a profile file")
    export.add_argument("-o", "--output", type=Path, default=Path("profile.json"))
    export.add_argument("--only", type=parse_only, default=set(BY_NAME), help=only_help)
    export.set_defaults(run=cmd_export)

    apply = commands.add_parser("apply", help="apply a profile file to this PC")
    apply.add_argument("profile", type=Path)
    apply.add_argument("--only", type=parse_only, default=set(BY_NAME), help=only_help)
    apply.add_argument("--dry-run", action="store_true", help="list what would change without changing it")
    apply.add_argument("--no-backup", action="store_true", help="skip saving current settings first")
    apply.set_defaults(run=cmd_apply)

    send = commands.add_parser("send", help="show a QR code and send this PC's settings to the phone app")
    send.add_argument("--only", type=parse_only, default=set(BY_NAME), help=only_help)
    send.add_argument("--port", type=int, default=0, help="port to listen on (default: any free port)")
    send.set_defaults(run=cmd_send)

    receive = commands.add_parser("receive", help="show a QR code and apply settings sent from the phone app")
    receive.add_argument("--only", type=parse_only, default=set(BY_NAME), help=only_help)
    receive.add_argument("--port", type=int, default=0, help="port to listen on (default: any free port)")
    receive.add_argument("--yes", action="store_true", help="apply without asking")
    receive.add_argument("--no-backup", action="store_true", help="skip saving current settings first")
    receive.set_defaults(run=cmd_receive)

    show_cmd = commands.add_parser("show", help="list what a profile file contains")
    show_cmd.add_argument("profile", type=Path)
    show_cmd.add_argument("--only", type=parse_only, default=set(BY_NAME), help=only_help)
    show_cmd.set_defaults(run=cmd_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
