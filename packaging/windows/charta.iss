; Installatore di Charta per Windows (Inno Setup 6).
; Si compila dalla cartella del progetto, dopo PyInstaller, con:
;   iscc /DAppVersion=0.3.0 packaging\windows\charta.iss
; Il risultato è dist\Charta-<versione>-windows-setup.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1F9E0A-3B7D-4E5A-9A61-CA4A2B7D0E31}
AppName=Charta
AppVersion={#AppVersion}
AppVerName=Charta {#AppVersion}
AppPublisher=EurekaFoundation
AppPublisherURL=https://github.com/EurekaFoundation/charta
AppSupportURL=https://github.com/EurekaFoundation/charta/issues
DefaultDirName={autopf}\Charta
DefaultGroupName=Charta
DisableProgramGroupPage=yes
; si installa anche senza diritti di amministratore (solo per l'utente)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=Charta-{#AppVersion}-windows-setup
SetupIconFile=..\icons\charta.ico
UninstallDisplayIcon={app}\Charta.exe
LicenseFile=..\..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
italian.AssocCharta=Apri i file .charta con Charta
english.AssocCharta=Open .charta files with Charta
italian.DocCharta=Documento Charta
english.DocCharta=Charta document

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "{cm:AssocCharta}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\Charta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Charta"; Filename: "{app}\Charta.exe"
Name: "{autodesktop}\Charta"; Filename: "{app}\Charta.exe"; Tasks: desktopicon

[Registry]
; doppio clic su un file .charta (per l'utente corrente: non servono diritti di amministratore)
Root: HKA; Subkey: "Software\Classes\.charta"; ValueType: string; ValueName: ""; ValueData: "Charta.Document"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Charta.Document"; ValueType: string; ValueName: ""; ValueData: "{cm:DocCharta}"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Charta.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\Charta.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\Charta.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Charta.exe"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\Charta.exe"; Description: "{cm:LaunchProgram,Charta}"; Flags: nowait postinstall skipifsilent
