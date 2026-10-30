; Windows installer for the QRPersonafy desktop app (Inno Setup 6).
; Installs the PyInstaller folder build for the current user, without admin rights.
; Build: iscc /DAppVersion=1.0.0 installer\qrpersonafy.iss   (after the pyinstaller step)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{C6078E46-D2FC-48D7-981C-82602A6F98D9}
AppName=QRPersonafy
AppVersion={#AppVersion}
AppPublisher=QRPersonafy contributors
AppPublisherURL=https://github.com/Slackpartistic/QRPersonafy
AppSupportURL=https://github.com/Slackpartistic/QRPersonafy/issues
DefaultDirName={autopf}\QRPersonafy
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=QRPersonafy-Setup-{#AppVersion}
SetupIconFile=qrpersonafy.ico
UninstallDisplayIcon={app}\QRPersonafy.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\QRPersonafy\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion createallsubdirs

[InstallDelete]
; Files from an older version that the new one no longer ships.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\QRPersonafy"; Filename: "{app}\QRPersonafy.exe"
Name: "{autodesktop}\QRPersonafy"; Filename: "{app}\QRPersonafy.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QRPersonafy.exe"; Description: "{cm:LaunchProgram,QRPersonafy}"; Flags: nowait postinstall skipifsilent
