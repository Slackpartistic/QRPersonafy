"""Writes the Windows version resource for QRPersonafy.exe (PyInstaller's --version-file).

Windows shows these fields under the file's Properties > Details, and code signing services
such as SignPath check that every build carries the product name and version.

Usage: python packaging/windows/version_info.py build/version_info.txt
"""

import sys
import tomllib
from pathlib import Path

# The one place the Windows file details take the app's name from.
PRODUCT_NAME = "QRPersonafy"
DESCRIPTION = "QRPersonafy: restore your desktop look from your phone"
COMPANY = "QRPersonafy contributors"

TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={nums},
    prodvers={nums},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', {company!r}),
        StringStruct('FileDescription', {description!r}),
        StringStruct('FileVersion', {version!r}),
        StringStruct('InternalName', {name!r}),
        StringStruct('LegalCopyright', 'MIT License'),
        StringStruct('OriginalFilename', {name!r} + '.exe'),
        StringStruct('ProductName', {name!r}),
        StringStruct('ProductVersion', {version!r})
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def render(version: str) -> str:
    parts = [int(p) for p in version.split(".")[:3]]
    nums = tuple(parts + [0] * (4 - len(parts)))
    return TEMPLATE.format(
        nums=nums, version=version, name=PRODUCT_NAME, description=DESCRIPTION, company=COMPANY
    )


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(version), encoding="utf-8")
    print(f"wrote {out} for {PRODUCT_NAME} {version}")


if __name__ == "__main__":
    main()
