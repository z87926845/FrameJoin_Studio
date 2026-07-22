#define MyAppName "FrameJoin Studio"
#define MyAppVersion GetEnv("APP_VERSION")
#define MySourceDir GetEnv("APP_SOURCE_DIR")
#define MyOutputDir GetEnv("APP_OUTPUT_DIR")
#define MyIconFile GetEnv("APP_ICON_FILE")
#define MyAppExeName "FrameJoinStudio.exe"

[Setup]
AppId={{32E3E4A7-C00F-4FBE-B035-07F9EF181751}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=刚学会说话的萌新
AppPublisherURL=https://github.com/z87926845/FrameJoin_Studio
AppSupportURL=https://github.com/z87926845/FrameJoin_Studio/issues
DefaultDirName={autopf}\FrameJoin Studio
DefaultGroupName=FrameJoin Studio
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#MyOutputDir}
OutputBaseFilename=FrameJoin_Studio_v{#MyAppVersion}_Windows_x64_Setup
SetupIconFile={#MyIconFile}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ChangesAssociations=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FrameJoin Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\FrameJoin Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,FrameJoin Studio}"; Flags: nowait postinstall skipifsilent
