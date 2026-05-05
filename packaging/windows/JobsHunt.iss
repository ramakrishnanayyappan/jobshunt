; JobsHunt Windows installer — builds a Start Menu entry and installs under Program Files.
; Prerequisites: run PyInstaller (see packaging/pyinstaller/jobshunt.spec) so dist\JobsHunt exists.
; Install Inno Setup (https://jrsoftware.org/isinfo.php), open this file, click Build → Compile.

#define MyAppName "JobsHunt"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "JobsHunt"
#define MyAppExeName "JobsHunt.exe"
#define BuildOutput "..\\pyinstaller\\dist\\JobsHunt"

[Setup]
AppId={{9F8E7D6C-5B4A-3210-FEDC-BA9876543210}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
; Stable filename for https://github.com/.../releases/latest/download/JobsHunt-Setup.exe
OutputBaseFilename=JobsHunt-Setup
SetupIconFile=..\icons\JobsHunt.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildOutput}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
