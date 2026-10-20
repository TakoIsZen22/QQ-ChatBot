param([switch]$Remove,[string]$IconPath)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$desktopFolder=[Environment]::GetFolderPath('Desktop')
$shell=New-Object -ComObject WScript.Shell
$menuFolder=Join-Path ([Environment]::GetFolderPath('Programs')) 'QQ ChatBot'
$shortcutPaths=@((Join-Path $desktopFolder 'QQ ChatBot.lnk'),(Join-Path $menuFolder 'QQ ChatBot.lnk'))
$oldMenuFolder=Join-Path ([Environment]::GetFolderPath('Programs')) '大肥鱼 Harness'
$oldShortcutPaths=@((Join-Path $desktopFolder '大肥鱼.lnk'),(Join-Path $oldMenuFolder '大肥鱼.lnk'))
function Test-OwnShortcut([string]$shortcutPath){
 if(-not (Test-Path -LiteralPath $shortcutPath)){return $false}
 $existing=$shell.CreateShortcut($shortcutPath)
 $targets=@((Join-Path $projectRoot '.venv\Scripts\pythonw.exe'),(Join-Path $projectRoot '.venv-desktop\Scripts\pythonw.exe'))
 if($existing.WorkingDirectory -eq $projectRoot -and $existing.TargetPath -eq (Join-Path $projectRoot 'QQ ChatBot.exe') -and -not $existing.Arguments){return $true}
 return ($existing.WorkingDirectory -eq $projectRoot -and $existing.Arguments -eq '-m src.desktop' -and ($targets -contains $existing.TargetPath))
}
if($Remove){
 foreach($shortcutPath in ($shortcutPaths+$oldShortcutPaths)){
  if(Test-OwnShortcut $shortcutPath){Remove-Item -LiteralPath $shortcutPath}
 }
 exit 0
}
foreach($shortcutPath in $shortcutPaths){
 if((Test-Path -LiteralPath $shortcutPath) -and -not (Test-OwnShortcut $shortcutPath)){throw 'QQ ChatBot 快捷方式属于其他位置，请先确认现有入口'}
}
$null=New-Item -ItemType Directory -Path $menuFolder -Force
if(-not $IconPath){
 $pythonPath=Join-Path $projectRoot '.venv\Scripts\python.exe'
 if(Test-Path -LiteralPath (Join-Path $projectRoot '_runtime\python.exe')){$pythonPath=Join-Path $projectRoot '_runtime\python.exe'}
 if(Test-Path -LiteralPath $pythonPath){
  [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
  $IconPath=& $pythonPath (Join-Path $projectRoot 'tools\icon-path.py')
  if($LASTEXITCODE -ne 0){throw '读取当前图标失败'}
 }else{$IconPath=Join-Path $projectRoot 'assets\xiaojing-user-icon.ico'}
}
$resolvedIcon=(Resolve-Path -LiteralPath $IconPath).Path
if(-not $resolvedIcon.StartsWith($projectRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetExtension($resolvedIcon) -ne '.ico'){throw '程序图标必须是项目内 ICO 文件'}
foreach($shortcutPath in $shortcutPaths){
$shortcut=$shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath="$projectRoot\.venv\Scripts\pythonw.exe"
$shortcut.Arguments='-m src.desktop'
if(Test-Path -LiteralPath (Join-Path $projectRoot 'QQ ChatBot.exe')){$shortcut.TargetPath=Join-Path $projectRoot 'QQ ChatBot.exe';$shortcut.Arguments=''}
$shortcut.WorkingDirectory=$projectRoot
$shortcut.Description='QQ ChatBot：对话、记忆、约定与运行控制台'
$shortcut.IconLocation="$resolvedIcon,0"
$shortcut.Save()
Write-Output $shortcutPath
}
foreach($shortcutPath in $oldShortcutPaths){
 if(Test-OwnShortcut $shortcutPath){Remove-Item -LiteralPath $shortcutPath}
}
