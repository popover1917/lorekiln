param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('session-start', 'user-prompt-submit', 'stop', 'session-end')]
    [string]$EventName
)

$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$eventJson = [Console]::In.ReadToEnd()
$pythonCandidates = @(
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    [Console]::Error.WriteLine('Lorekiln could not locate a Python runtime.')
    exit 1
}
$runtime = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\memory_runtime.py'
$eventJson | & $python $runtime hook $EventName
$runtimeExitCode = $LASTEXITCODE
if ($runtimeExitCode -ne 0) {
    $pluginData = if ($env:PLUGIN_DATA) { $env:PLUGIN_DATA } elseif ($env:CLAUDE_PLUGIN_DATA) { $env:CLAUDE_PLUGIN_DATA } else { $null }
    if ($pluginData) {
        try {
            New-Item -ItemType Directory -Path $pluginData -Force | Out-Null
            $failure = [ordered]@{
                at = [DateTime]::UtcNow.ToString('o')
                event = $EventName
                exit_code = $runtimeExitCode
                message = 'Lorekiln hook runtime exited unsuccessfully.'
            } | ConvertTo-Json -Compress
            Add-Content -LiteralPath (Join-Path $pluginData 'hook-bootstrap-errors.jsonl') -Value $failure -Encoding utf8
        } catch {
            [Console]::Error.WriteLine("Lorekiln could not record hook failure: $($_.Exception.Message)")
        }
    }
}
exit $runtimeExitCode
