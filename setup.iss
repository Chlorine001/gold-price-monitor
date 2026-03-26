[Setup]
AppName=金价监控
AppVersion=6.1
DefaultDirName={pf}\GoldMonitor
DefaultGroupName=金价监控
UninstallDisplayIcon={app}\GoldMonitor.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.
OutputBaseFilename=GoldMonitor_Setup

[Files]
Source: "dist\GoldMonitor.exe"; DestDir: "{app}"; Flags: ignoreversion
; 如果需要包含其他文件（如说明文档），可在此添加
; Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\金价监控"; Filename: "{app}\GoldMonitor.exe"
Name: "{group}\卸载金价监控"; Filename: "{uninstallexe}"
Name: "{userdesktop}\金价监控"; Filename: "{app}\GoldMonitor.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: unchecked

[Run]
Filename: "{app}\GoldMonitor.exe"; Description: "立即启动金价监控"; Flags: postinstall nowait skipifsilent