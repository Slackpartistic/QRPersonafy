# Getting rid of the install warnings

Today, people installing QRPersonafy see two warnings:

- **Windows SmartScreen** ("Windows protected your PC"), because the Windows files aren't
  code-signed.
- **Google Play Protect** ("Unsafe app blocked" / "App scan recommended"), because Google has
  never seen the APK in the Play Store.

The README's [Seeing a warning?](../README.md#seeing-a-warning) section tells users how to get
past them safely. This page is for the maintainer: how to make them go away.

| | Chosen | Cost | Why |
| --- | --- | --- | --- |
| Windows | **SignPath Foundation** | Free | Free for open-source projects, works from GitHub Actions, and available worldwide. Azure Artifact Signing only signs for individuals in the USA and Canada. |
| Android | **Google Play** | US$25 once | Play Protect trusts Play apps, and a Play developer account also covers Google's new developer verification for sideloaded apps (from 2027). F-Droid would first need the QR scanner replaced (see below). |

The repository is already set up for both: signing switches itself on once the settings below
exist, and release builds include the Play app bundle.

## Step 0: decide the name first

If the app is going to be renamed, do it **before** applying to SignPath and before creating
the Play listing. Things tied to the name:

| Thing | Can it change later? |
| --- | --- |
| Android package ID `io.github.slackpartistic.qrpersonafy` (in `mobile/android/app/build.gradle.kts`) | **No**, not once it's on Google Play or registered with Google's developer verification. Users never see it, so it's fine to keep it even if the app is renamed. Changing it now would also mean current users can't update: they'd have to back up, uninstall and reinstall. |
| Play Store title and listing | Yes, any time, but each change is reviewed again. |
| SignPath project | SignPath reviews the project under its name and GitHub URL. Renaming afterwards means telling them and possibly a new review. |
| Name inside the signed `.exe` (Properties → Details) | Yes. It's set in one place: `desktop/packaging/windows/version_info.py`. |
| Windows installer `AppId` GUID in `desktop/installer/qrpersonafy.iss` | Keep it whatever the name: it's how Windows knows a new version replaces the old one. |
| GitHub repository name | Yes; GitHub redirects old links. Do it before applying to SignPath. |

## Part 1: sign the Windows app with SignPath Foundation (free)

What users get: the installer and `QRPersonafy.exe` show **SignPath Foundation** as the verified
publisher instead of "Unknown publisher". SmartScreen trusts signed files much sooner, but a
brand-new release can still show the warning for its first downloads while Microsoft builds up
reputation for it.

What it costs you: nothing, but SignPath's rules say **each release needs you to approve the
signing by hand**. The Release workflow pauses twice per release (once for the app, once for the
installer) and waits up to an hour for each approval.

### 1. Get ready

1. Turn on two-factor authentication on GitHub if it isn't already: **GitHub → Settings →
   Password and authentication → Enable two-factor authentication**. SignPath requires it.
2. Make sure the [code signing policy](code-signing-policy.md) and [privacy policy](privacy.md)
   pages are on `main` (they come with this change) and that the README links to them (it does).

### 2. Apply

1. Go to <https://signpath.org> and open the application for free open-source code signing.
2. Fill in the form. Useful answers:
   - Project: QRPersonafy (or the new name), <https://github.com/Slackpartistic/QRPersonafy>
   - License: MIT
   - Build: GitHub Actions on GitHub-hosted runners (`.github/workflows/release.yml`)
   - What's signed: the Windows installer and app `.exe`
   - Code signing policy: link to `docs/code-signing-policy.md` on GitHub
3. Wait for their reply. It can take a few days to a few weeks. They may ask questions by email.

### 3. Set up the SignPath project (after you're accepted)

1. Sign in at <https://app.signpath.io> and turn on multi-factor authentication for your account
   when it asks.
2. Install the **SignPath GitHub App** on the QRPersonafy repository when SignPath asks you to
   (it lets SignPath check that files really came from this repository's workflow).
3. Open the project SignPath created for you. Note three things, you'll need them in step 4:
   - the **Organization ID** (under your organization's settings),
   - the **project slug** (the workflow assumes `QRPersonafy`),
   - the **signing policy slug** for releases (the workflow assumes `release-signing`).
4. Under the project's **Artifact configurations**, add two, pasting the files from this
   repository:
   - slug **`app-folder`**: the contents of `.signpath/artifact-configurations/app-folder.xml`
   - slug **`installer`**: the contents of `.signpath/artifact-configurations/installer.xml`
5. Make sure the project's **trusted build system** is *GitHub.com* (SignPath Foundation usually
   sets this up).
6. Create an **API token** for a user that is allowed to *submit* signing requests on the
   release signing policy (in SignPath, under **Users**: your own user or a new CI user). Copy
   it straight away; it's shown only once.

### 4. Add the settings to GitHub

In the repository: **Settings → Secrets and variables → Actions**.

1. **Secrets** tab → **New repository secret**:
   - `SIGNPATH_API_TOKEN` = the API token from step 3.6
2. **Variables** tab → **New repository variable**:
   - `SIGNPATH_ORGANIZATION_ID` = the Organization ID
   - `SIGNPATH_PROJECT_SLUG`, only if your project slug isn't `QRPersonafy`
   - `SIGNPATH_POLICY_SLUG`, only if your signing policy slug isn't `release-signing`

Nothing changes for pull requests or pushes to `main`: only release tags are signed.

### 5. Your next release

1. Release as usual ([releasing.md](releasing.md)): set the versions, merge, push the tag.
2. Watch the **Release** run on GitHub. When the Windows job reaches **Sign QRPersonafy.exe
   (approve the request in SignPath)**, open <https://app.signpath.io> → **Signing requests**,
   open the new one and press **Approve**.
3. A few minutes later it reaches **Sign the installer**: approve that one too.
4. When the draft release appears, download the installer on Windows, right-click it →
   **Properties → Digital Signatures**. It should list **SignPath Foundation**. Then publish.
5. Remove the "Status: applied for" note at the top of `code-signing-policy.md`.

If you miss an approval, the job fails after an hour. Re-run the failed job from the run's page
(**Re-run failed jobs**) and approve the new request.

## Part 2: publish the phone app on Google Play (US$25 once)

What users get: installing from the Play Store gives no warnings at all, and updates arrive
automatically. If you keep offering the APK on GitHub too, signed with the same key, it's the
same app as far as Android is concerned.

It also prepares for **Google's Android developer verification**. From 2027 (already rolling out
in Brazil, Indonesia, Singapore and Thailand since 30 September 2026), certified Android phones
will only install apps from verified developers without extra steps; unregistered apps need a
special "advanced flow" or a computer with ADB. A verified Play account covers this, and Google
registers your Play apps automatically.

### 1. Create the developer account

1. Go to <https://play.google.com/console/signup> and sign in with the Google account you want
   to own the app.
2. Choose **Yourself** (a personal account), pay the **US$25** one-time fee, and complete the
   identity check (Google asks for ID and confirms your phone number and an Android device). It
   can take a few days.

### 2. Create the app

1. In Play Console: **Create app**. App name: the chosen name. Default language: English. App,
   Free. Accept the declarations.
2. **Store listing** (Grow users → Store presence → Main store listing): copy the text from
   `mobile/fastlane/metadata/android/en-US/` (title, short description, full description). You
   also need:
   - the app icon, 512 × 512 PNG,
   - a feature graphic, 1024 × 500 PNG (a simple banner with the name is fine),
   - 2 to 8 phone screenshots (take them on your phone: welcome, saved PCs, restoring, done).
3. **App content** (Policy → App content), answer each item:
   - Privacy policy: `https://github.com/Slackpartistic/QRPersonafy/blob/main/docs/privacy.md`
   - Ads: no ads
   - App access: "All or some functionality is restricted". Explain that the app pairs with the
     free desktop app from the GitHub page by scanning a QR code on a PC on the same Wi-Fi.
   - Content rating: fill in the questionnaire (category Utility; answer No to everything).
   - Target audience: 13 and over (or 18 and over).
   - Data safety: **No data collected, no data shared** (everything stays on the phone or goes
     to the user's own server, encrypted). Data encrypted in transit: yes.
   - Government, financial, health, news apps: no.

### 3. Use the same signing key as the GitHub APK

Google re-signs Play apps. Let it use **your existing key**, so the Play version and the GitHub
APK can update each other:

1. When you create your first release, Play Console shows **Play App Signing**. Choose
   **Change app signing key → Export and upload a key from Java keystore**.
2. Follow the instructions on that page: download Google's `pepk.jar` and run the command it
   shows against your `qrpersonafy-release.jks` (the alias is `qrpersonafy`). Upload the
   resulting zip.
3. As the upload key, use the same `.jks`. The app bundle the Release workflow builds is already
   signed with it.

### 4. Get the app bundle

Every release run now also builds a Play app bundle. In a web browser (the GitHub mobile app
can't download these), open the **Release** run under **Actions**, scroll to **Artifacts**, and
download **qrpersonafy-android-play-bundle**. Unzip it to get `app-release.aab`. Artifacts are
kept for 90 days.

### 5. Closed test, then production

Google currently requires new personal accounts to run a **closed test with at least 12 testers
for 14 days** before the app can go public.

1. **Test and release → Testing → Closed testing → Create track**. Add testers by email (friends
   and family with Android phones; a Google Group works too).
2. **Create release**, upload `app-release.aab`, add release notes, roll it out.
3. Send testers the opt-in link from the track's page. They join, install from the Play Store,
   and keep it installed for 14 days.
4. After 14 days, **Dashboard → Apply for production** and answer the questions about the test.
5. Once approved: **Production → Create release**, upload the bundle from the latest release
   run, and roll out. The first review usually takes a few days.

For later releases, repeat step 4 and **Production → Create release** each time. The version
code must go up every release; raising the `+N` in `mobile/pubspec.yaml` does that.

## Why not the other options

**Azure Artifact Signing** (formerly Trusted Signing, about US$9.99 a month) signs for
individual developers only in the USA and Canada. Organizations in Australia can apply, but
whether a sole trader qualifies isn't confirmed. Worth revisiting if that changes, because the
publisher would show your own name instead of SignPath Foundation.

**A regular code-signing certificate** (OV, from about US$150–300 a year) works worldwide but
needs a hardware token or cloud key, and doesn't remove SmartScreen warnings any faster.

**F-Droid** is free and popular with open-source fans, but:

- it only accepts apps with no closed-source parts, and the phone app's QR scanner
  (`mobile_scanner`) uses Google's closed-source ML Kit on Android, so it would first need a
  different, open-source scanner;
- F-Droid builds and signs the app with its own key, so F-Droid and GitHub/Play installs can't
  update each other;
- its future under Google's developer verification is still unclear.

It could still be added later as a second channel once the scanner is swapped. The store text in
`mobile/fastlane/` is already in the layout F-Droid reads.
