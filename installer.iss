; Instalador Inno Setup do MarcosDown
#define AppName "MarcosDown"
#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif

[Setup]
AppId={{4D7E1B93-2A6C-4F58-8E0D-71C3B5A9E6F2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Liraprint
DefaultDirName={autopf}\MarcosDown
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\MarcosDown.exe
OutputDir=Output
OutputBaseFilename=MarcosDown-Setup-{#AppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked
Name: "sendto"; Description: "Adicionar ao menu ""Enviar para"" do Windows Explorer"

[Files]
Source: "dist\MarcosDown\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\MarcosDown.exe"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\MarcosDown.exe"; Tasks: desktopicon
Name: "{usersendto}\Converter para Markdown"; Filename: "{app}\MarcosDown.exe"; Tasks: sendto

[Run]
Filename: "{app}\MarcosDown.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
