# Releasing

1. Set the version in `desktop/pyproject.toml`, `desktop/src/qrpersonafy/__init__.py` and
   `mobile/pubspec.yaml` (`X.Y.Z+N`, raising the build number `N` each release). Merge that.
2. Tag the merge commit and push the tag:

   ```
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

3. The **Release** workflow checks the tag matches the versions, runs both apps' tests, builds
   the Windows installer, the portable zip, the Linux AppImage and tarball and the signed APK,
   and creates a **draft** GitHub Release with them and `SHA256SUMS.txt`.
4. Open the draft under **Releases**, edit the notes, try the files, and press **Publish**.

## Android signing key (one-time setup)

Android only installs an update over an existing app if both are signed with the same key,
so every release must use the same one. Create it once, on your own computer:

```
keytool -genkeypair -v -keystore qrpersonafy-release.jks -alias qrpersonafy \
  -keyalg RSA -keysize 4096 -validity 10000
```

(`keytool` comes with any Java JDK, including the one Android Studio bundles.)

**Back up the `.jks` file and its passwords somewhere safe.** If they're lost, users have to
uninstall the app (losing their saved PCs unless they use backup) to install new versions.

Then add four repository secrets in **Settings → Secrets and variables → Actions**:

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | the `.jks` file in base64 (`base64 -w0 qrpersonafy-release.jks` on Linux, `[Convert]::ToBase64String([IO.File]::ReadAllBytes("qrpersonafy-release.jks"))` in PowerShell) |
| `ANDROID_KEYSTORE_PASSWORD` | the keystore password |
| `ANDROID_KEY_ALIAS` | `qrpersonafy` |
| `ANDROID_KEY_PASSWORD` | the key password (the same as the keystore password unless you chose another) |

Without these secrets, CI builds are signed with a throwaway debug key: fine for testing,
but not for releases.
