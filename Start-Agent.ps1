$ErrorActionPreference = 'Stop'
$geminiPointer = [IntPtr]::Zero
$cloudflarePointer = [IntPtr]::Zero
try {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { $pythonCmd = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $pythonCmd) { throw 'Python was not found. Install Python 3, then run this launcher again.' }

    Write-Host 'Orbit uses Gemini for text and Cloudflare Workers AI for images.' -ForegroundColor Cyan
    Write-Host 'Use the providers’ free plans. Orbit will not fall back to paid models.' -ForegroundColor Gray
    $geminiSecure = Read-Host 'Paste your Google Gemini API key (hidden input)' -AsSecureString
    $geminiPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($geminiSecure)
    $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($geminiPointer)

    $env:CLOUDFLARE_ACCOUNT_ID = (Read-Host 'Paste your Cloudflare Account ID').Trim()
    $cloudflareSecure = Read-Host 'Paste your Cloudflare Workers AI API token (hidden input)' -AsSecureString
    $cloudflarePointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($cloudflareSecure)
    $env:CLOUDFLARE_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($cloudflarePointer)

    if (-not $env:GEMINI_API_KEY -or -not $env:CLOUDFLARE_ACCOUNT_ID -or -not $env:CLOUDFLARE_API_TOKEN) {
        throw 'All three values are required. Create the keys in Google AI Studio and Cloudflare, then start Orbit again.'
    }

    $serverFile = Join-Path $PSScriptRoot 'agent_server.py'
    if ($pythonCmd.Name -eq 'py.exe') { & $pythonCmd.Source -3 $serverFile }
    else { & $pythonCmd.Source $serverFile }
    if ($LASTEXITCODE -ne 0) { throw "The local agent stopped with exit code $LASTEXITCODE." }
}
catch {
    Write-Host "`nAgent startup error: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if ($geminiPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($geminiPointer) }
    if ($cloudflarePointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($cloudflarePointer) }
    Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:CLOUDFLARE_ACCOUNT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:CLOUDFLARE_API_TOKEN -ErrorAction SilentlyContinue
}
Write-Host "`nThe agent has stopped. Press Enter to close this window." -ForegroundColor Yellow
Read-Host | Out-Null
