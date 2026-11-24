; Windows installer for the QRestoa desktop app (Inno Setup 6).
; Installs the PyInstaller folder build for the current user, without admin rights.
; Build: iscc /DAppVersion=1.0.0 installer\qrestoa.iss   (after the pyinstaller step)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{C6078E46-D2FC-48D7-981C-82602A6F98D9}
AppName=QRestoa
AppVersion={#AppVersion}
AppPublisher=QRestoa contributors
AppPublisherURL=https://github.com/Slackpartistic/QRestoa
AppSupportURL=https://github.com/Slackpartistic/QRestoa/issues
DefaultDirName={autopf}\QRestoa
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=QRestoa-Setup-{#AppVersion}
SetupIconFile=qrestoa.ico
UninstallDisplayIcon={app}\QRestoa.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\QRestoa\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[InstallDelete]
; Files from an older version that the new one no longer ships.
Type: filesandordirs; Name: "{app}\_internal"
; The app was called QRPersonafy before 1.2. An update keeps the same folder (same AppId) but
; takes away the old program and its shortcuts, so only the QRestoa ones are left.
Type: files; Name: "{app}\QRPersonafy.exe"
Type: files; Name: "{autoprograms}\QRPersonafy.lnk"
Type: files; Name: "{autodesktop}\QRPersonafy.lnk"

[Icons]
Name: "{autoprograms}\QRestoa"; Filename: "{app}\QRestoa.exe"
Name: "{autodesktop}\QRestoa"; Filename: "{app}\QRestoa.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QRestoa.exe"; Description: "{cm:LaunchProgram,QRestoa}"; Flags: nowait postinstall skipifsilent
