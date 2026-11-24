# Code signing policy

> **Status:** applied for. Until SignPath Foundation accepts the project, Windows release files
> are unsigned and this policy describes how they will be signed. Remove this note when the
> first signed release is out.

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).

## What is signed

Only the Windows files on this repository's
[Releases page](https://github.com/Slackpartistic/QRPersonafy/releases): `QRPersonafy.exe`
(inside the installer and the portable zip) and `QRPersonafy-Setup-<version>.exe`. They are built
from this repository's source by the public [Release workflow](../.github/workflows/release.yml)
on GitHub-hosted runners, and sent to SignPath from there. Nothing built on a personal computer
is signed.

## Team roles

| Role | Who |
| --- | --- |
| Committers and reviewers | [Slackpartistic](https://github.com/Slackpartistic) |
| Approvers | [Slackpartistic](https://github.com/Slackpartistic) |

Changes from anyone outside the team are reviewed by a team member before they are merged. Every
signing request is approved by hand in SignPath. All team members use multi-factor
authentication on GitHub and SignPath.

## Privacy

This program will not transfer any information to other networked systems unless specifically
requested by the user or the person installing or operating it. See the
[privacy policy](privacy.md) for exactly what the apps send and where.
