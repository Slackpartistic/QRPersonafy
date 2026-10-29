"""Command line: qrpersonafy export | apply | show."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .profile import apply_profile, export_profile, load_profile, save_profile
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


def cmd_apply(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    if args.dry_run:
        return show(profile, args.only)
    ctx = windows_context()
    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = ctx.system.localappdata / "QRPersonafy" / "backups" / f"before-apply-{stamp}.json"
        save_profile(export_profile(ctx, args.only), backup)
        print(f"Backed up current settings to {backup}")
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
