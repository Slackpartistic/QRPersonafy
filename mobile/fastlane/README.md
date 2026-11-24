# Store listing

The app's store listing text, in the standard
[fastlane](https://docs.fastlane.tools/actions/supply/) layout that both Google Play tools and
F-Droid read:

- `metadata/android/en-US/title.txt`: app name (max 30 characters)
- `short_description.txt`: one line (max 80 characters)
- `full_description.txt`: the full description (max 4000 characters)
- `changelogs/<build number>.txt`: what's new, one file per release, named after the build
  number after the `+` in `pubspec.yaml` (max 500 characters)

To publish to Google Play, copy these into Play Console's store listing; see
[docs/signing.md](../../docs/signing.md).

Screenshots go in `metadata/android/en-US/images/phoneScreenshots/` (PNG, 2 to 8 of them), with
the 512 × 512 icon at `images/icon.png` and the 1024 × 500 banner at `images/featureGraphic.png`.
