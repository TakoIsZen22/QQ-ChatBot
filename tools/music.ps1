param([ValidateSet('status','next','previous','play','pause')][string]$Action='status')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,Windows.Media.Control,ContentType=WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'} | Select-Object -First 1)
function Await-WinRT($Operation, $Type) {
    $task = $asTask.MakeGenericMethod($Type).Invoke($null,@($Operation))
    $task.GetAwaiter().GetResult()
}
$manager = Await-WinRT ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
$session = $manager.GetSessions() | Where-Object {$_.SourceAppUserModelId -match 'cloudmusic|netease'} | Select-Object -First 1
if (-not $session) { throw '未发现网易云 SMTC 会话；请打开网易云播放并启用系统媒体集成。该客户端若不支持 SMTC，不能读取。' }
if ($Action -ne 'status') {
    $op = switch($Action) {'next' {$session.TrySkipNextAsync()} 'previous' {$session.TrySkipPreviousAsync()} 'play' {$session.TryPlayAsync()} 'pause' {$session.TryPauseAsync()}}
    $ok = Await-WinRT $op ([bool])
    if (-not $ok) {throw '网易云拒绝控制动作'}
}
$media = Await-WinRT ($session.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
@{title=$media.Title;artist=$media.Artist;album=$media.AlbumTitle;source=$session.SourceAppUserModelId;status=$session.GetPlaybackInfo().PlaybackStatus.ToString()} | ConvertTo-Json -Compress
