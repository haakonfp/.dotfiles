<#
.SYNOPSIS
Installs the JetBrainsMono Nerd Font Mono family for the current Windows user.
.EXAMPLE
.\Install-Fonts.ps1 -SourceDirectory 'C:\Users\Your Name\Downloads\fonts'
.EXAMPLE
.\Install-Fonts.ps1 -Check
.NOTES
No administrator privileges required. SourceDirectory must contain all 16 Mono
TTFs and OFL.txt from the checksum-verified Nerd Fonts 3.5.1 archive.
Use -WhatIf to preview without copying, registration or font broadcasts.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $SourceDirectory,
    [switch] $Check
)
$ErrorActionPreference = 'Stop'
$styles = @('Thin', 'ThinItalic', 'ExtraLight', 'ExtraLightItalic', 'Light', 'LightItalic',
            'Regular', 'Italic', 'Medium', 'MediumItalic', 'SemiBold', 'SemiBoldItalic',
            'Bold', 'BoldItalic', 'ExtraBold', 'ExtraBoldItalic')
$destination = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
$registry = 'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'

if ($Check) {
    Add-Type -AssemblyName System.Drawing
    $collection = New-Object System.Drawing.Text.InstalledFontCollection
    try {
        $found = @($collection.Families | Where-Object {
            $_.Name -eq 'JetBrainsMono Nerd Font Mono' -or $_.Name -eq 'JetBrainsMono NFM'
        })
        if ($found.Count -eq 0) {
            Write-Output 'JetBrainsMono Nerd Font Mono is missing. Run the installer, then restart Windows Terminal.'
            exit 1
        }
        Write-Output 'JetBrainsMono Nerd Font Mono is available on this Windows host.'
        $perUserCount = @($styles | Where-Object {
            Test-Path -LiteralPath (Join-Path $destination "JetBrainsMonoNerdFontMono-$_.ttf") -PathType Leaf
        }).Count
        Write-Output "Per-user managed variants: $perUserCount / 16 (a system installation may supply the family)."
        exit 0
    } finally {
        $collection.Dispose()
    }
}
if ([string]::IsNullOrWhiteSpace($SourceDirectory)) {
    throw 'Provide -SourceDirectory with the verified Mono font files, or use -Check.'
}
$SourceDirectory = (Resolve-Path -LiteralPath $SourceDirectory).Path
$license = Join-Path $SourceDirectory 'OFL.txt'
if (!(Test-Path -LiteralPath $license -PathType Leaf)) {
    throw 'Missing upstream OFL.txt; use scripts/install-fonts.sh --windows from WSL.'
}
# Preflight the complete family before the first write; do not install NL/Propo fonts.
$fonts = @($styles | ForEach-Object {
    $font = Join-Path $SourceDirectory "JetBrainsMonoNerdFontMono-$_.ttf"
    if (!(Test-Path -LiteralPath $font -PathType Leaf) -or (Get-Item -LiteralPath $font).Length -eq 0) {
        throw "Missing Mono font variant: $_"
    }
    Get-Item -LiteralPath $font
})
if (!$PSCmdlet.ShouldProcess("$destination and $registry", 'Install/register all 16 Mono font variants for the current user')) {
    return
}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class DotfilesFontNative {
    [DllImport("gdi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int AddFontResourceEx(string file, uint flags, IntPtr reserved);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint message, UIntPtr wparam,
        IntPtr lparam, uint flags, uint timeout, out UIntPtr result);
}
'@
New-Item -ItemType Directory -Path $destination -Force | Out-Null
# Registry-provider New-Item -Force replaces an existing key and its values.
# Create only an absent key; never reset another application's registrations.
if (!(Test-Path -LiteralPath $registry)) {
    New-Item -Path $registry | Out-Null
}
$changed = 0
foreach ($font in $fonts) {
    $target = Join-Path $destination $font.Name
    $same = (Test-Path -LiteralPath $target -PathType Leaf) -and (
        (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -eq
        (Get-FileHash -LiteralPath $font.FullName -Algorithm SHA256).Hash)
    $style = $font.BaseName -replace '^JetBrainsMonoNerdFontMono-', ''
    $style = $style -creplace 'Italic$', ' Italic'
    $valueName = "JetBrainsMono Nerd Font Mono $($style.Trim()) (TrueType)"
    # A missing value is normal on first install. Windows PowerShell can throw
    # from Get-ItemPropertyValue even with -ErrorAction SilentlyContinue.
    $registered = (Get-Item -LiteralPath $registry).GetValue($valueName, $null)
    if (!$same) {
        try {
            Copy-Item -LiteralPath $font.FullName -Destination $target -Force
        } catch {
            throw "Cannot update '$target'. Close font-using applications or restart Windows, then retry. $($_.Exception.Message)"
        }
    }
    if (!$same -or $registered -ne $target) {
        if ([DotfilesFontNative]::AddFontResourceEx($target, 0, [IntPtr]::Zero) -eq 0) {
            throw "Windows could not load '$target'; the copy remains for inspection."
        }
        New-ItemProperty -LiteralPath $registry -Name $valueName -Value $target -PropertyType String -Force | Out-Null
        $changed++
    }
}
$licenseDirectory = Join-Path $destination 'JetBrainsMono-Nerd-Licenses'
New-Item -ItemType Directory -Path $licenseDirectory -Force | Out-Null
Copy-Item -LiteralPath $license -Destination (Join-Path $licenseDirectory 'OFL.txt') -Force
$readme = Join-Path $SourceDirectory 'README-upstream.md'
if (Test-Path -LiteralPath $readme -PathType Leaf) {
    Copy-Item -LiteralPath $readme -Destination (Join-Path $licenseDirectory 'README-upstream.md') -Force
}
if ($changed -gt 0) {
    $broadcastResult = [UIntPtr]::Zero
    # HWND_BROADCAST, WM_FONTCHANGE, SMTO_ABORTIFHUNG; bounded for unresponsive apps.
    [void][DotfilesFontNative]::SendMessageTimeout([IntPtr]0xffff, 0x001D, [UIntPtr]::Zero,
        [IntPtr]::Zero, 0x0002, 1000, [ref]$broadcastResult)
}
Write-Output "Windows Mono fonts ready (16 variants, $changed installed/registered). Restart Windows Terminal if already running."
