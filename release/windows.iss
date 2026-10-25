; Per-user installer. Persistent data is stored separately from program files.
#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif
[Setup]
AppId=MajsoulHook
AppName=Majsoul Hook
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\MajsoulHook
DefaultGroupName=Majsoul Hook
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
OutputDir={#OutputDir}
OutputBaseFilename=majsoul-hook-{#AppVersion}-windows-x64-installer
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\majsoul-hook-gui.exe
LicenseFile={#SourceDir}\LICENSE
[Tasks]
Name: desktopicon; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Majsoul Hook"; Filename: "{app}\majsoul-hook-gui.exe"
Name: "{autodesktop}\Majsoul Hook"; Filename: "{app}\majsoul-hook-gui.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\majsoul-hook-gui.exe"; Description: "Open Majsoul Hook"; Flags: nowait postinstall skipifsilent
