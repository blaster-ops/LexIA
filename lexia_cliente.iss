; =============================================================================
; Proyecto: LexIA - Emerald Systems
; Script de Instalación - Inno Setup Compiler
; Autor: José Miguel Tapia Adán
; Institución: Universidad Tecnológica de Tehuacán (UTT)
; =============================================================================

[Setup]
AppName=LexIA - Emerald Systems
AppVersion=1.1
AppPublisher=Emerald Systems
DefaultDirName={autopf}\LexIA_Emerald_Systems
DefaultGroupName=LexIA - Emerald Systems
DisableProgramGroupPage=yes
OutputDir=C:\ISS
OutputBaseFilename=Instalador_LexIA
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=static\LogoLexIA.ico
UninstallDisplayIcon={app}\cliente_lexia.exe

[Files]
; Solo copiamos el ejecutable compilado y recursos necesarios, no el código fuente ni el venv.
Source: "dist\cliente_lexia.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "static\LogoLexIA.ico"; DestDir: "{app}\static"; Flags: ignoreversion
Source: "lexia_config.json"; DestDir: "{app}"; Flags: ignoreversion uninsneveruninstall

[Icons]
; Acceso directo apuntando al ejecutable compilado
Name: "{autodesktop}\LexIA - Emerald Systems"; Filename: "{app}\cliente_lexia.exe"; WorkingDir: "{app}"; IconFilename: "{app}\static\LogoLexIA.ico"
Name: "{group}\LexIA - Emerald Systems"; Filename: "{app}\cliente_lexia.exe"; WorkingDir: "{app}"; IconFilename: "{app}\static\LogoLexIA.ico"

[Run]
; Lanzar la app compilada al terminar la instalación
Description: "{cm:LaunchProgram,LexIA - Emerald Systems}"; Filename: "{app}\cliente_lexia.exe"; Flags: postinstall nowait skipifsilent
