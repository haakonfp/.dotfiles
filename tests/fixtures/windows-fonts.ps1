# Run the real installer with only Windows registry/native APIs substituted.
param(
    [Parameter(Mandatory = $true)][string] $Installer,
    [Parameter(Mandatory = $true)][string] $FixtureRoot,
    [ValidateSet('fresh', 'partial', 'denied')][string] $Scenario = 'fresh'
)
$ErrorActionPreference = 'Stop'
$env:LOCALAPPDATA = Join-Path $FixtureRoot 'local app data'
$source = Join-Path $FixtureRoot 'source fonts'
$destination = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
New-Item -ItemType Directory -Path $source -Force | Out-Null
$styles = @('Thin', 'ThinItalic', 'ExtraLight', 'ExtraLightItalic', 'Light', 'LightItalic',
            'Regular', 'Italic', 'Medium', 'MediumItalic', 'SemiBold', 'SemiBoldItalic',
            'Bold', 'BoldItalic', 'ExtraBold', 'ExtraBoldItalic')
foreach ($style in $styles) {
    Set-Content -LiteralPath (Join-Path $source "JetBrainsMonoNerdFontMono-$style.ttf") -Value "fixture $style"
}
Set-Content -LiteralPath (Join-Path $source 'OFL.txt') -Value 'fixture license'
$script:registrations = @{'Unrelated Font (TrueType)' = 'keep.ttf'}
$script:registryExists = $false
$script:denied = $Scenario -eq 'denied'
$script:writes = 0
Add-Type -TypeDefinition @'
using System;
public static class DotfilesFontNative {
    public static int Loads;
    public static int AddFontResourceEx(string file, uint flags, IntPtr reserved) {
        Loads++; return 1;
    }
    public static IntPtr SendMessageTimeout(IntPtr hwnd, uint message, UIntPtr wparam,
        IntPtr lparam, uint flags, uint timeout, out UIntPtr result) {
        result = UIntPtr.Zero; return IntPtr.Zero;
    }
}
'@
function Add-Type { param([string] $TypeDefinition) }
function Test-Path {
    [CmdletBinding()]
    param([string] $LiteralPath, [string] $PathType)
    if ($LiteralPath -like 'HKCU:*') { return $script:registryExists }
    Microsoft.PowerShell.Management\Test-Path @PSBoundParameters
}
function New-Item {
    [CmdletBinding()]
    param([string] $Path, [string] $ItemType, [switch] $Force)
    if ($Path -like 'HKCU:*') {
        if ($Force) { throw 'Registry key must never be reset' }
        $script:registryExists = $true
        return
    }
    Microsoft.PowerShell.Management\New-Item @PSBoundParameters
}
function Get-ItemPropertyValue {
    [CmdletBinding()]
    param([string] $LiteralPath, [string] $Name)
    if ($script:denied) { throw [System.UnauthorizedAccessException]::new('Fixture registry access denied') }
    if (!$script:registrations.ContainsKey($Name)) {
        # Windows PowerShell throws even with -ErrorAction SilentlyContinue.
        $errorRecord = [System.Management.Automation.ErrorRecord]::new(
            [System.Management.Automation.PSArgumentException]::new("Property $Name does not exist"),
            'Argument,Microsoft.PowerShell.Commands.GetItemPropertyValueCommand',
            [System.Management.Automation.ErrorCategory]::InvalidArgument, $Name)
        $PSCmdlet.ThrowTerminatingError($errorRecord)
    }
    $script:registrations[$Name]
}
function Get-Item {
    [CmdletBinding()]
    param([string] $LiteralPath)
    if ($LiteralPath -like 'HKCU:*') {
        if ($script:denied) { throw [System.UnauthorizedAccessException]::new('Fixture registry access denied') }
        $key = [PSCustomObject]@{Values = $script:registrations}
        $key | Add-Member -MemberType ScriptMethod -Name GetValue -Value {
            param($name, $defaultValue)
            if ($this.Values.ContainsKey($name)) { return $this.Values[$name] }
            return $defaultValue
        }
        return $key
    }
    Microsoft.PowerShell.Management\Get-Item @PSBoundParameters
}
function New-ItemProperty {
    [CmdletBinding()]
    param([string] $LiteralPath, [string] $Name, [string] $Value, [string] $PropertyType, [switch] $Force)
    if ($LiteralPath -notlike 'HKCU:*' -or $PropertyType -ne 'String') { throw 'Unexpected registry write' }
    $script:registrations[$Name] = $Value
    $script:writes++
}
if ($Scenario -eq 'partial') {
    $script:registryExists = $true
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    foreach ($style in $styles) {
        $name = "JetBrainsMonoNerdFontMono-$style.ttf"
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $destination $name)
        if ($style -ne 'Thin') {
            $label = ($style -creplace 'Italic$', ' Italic').Trim()
            $script:registrations["JetBrainsMono Nerd Font Mono $label (TrueType)"] = Join-Path $destination $name
        }
    }
}
if ($Scenario -eq 'denied') {
    try {
        . $Installer -SourceDirectory $source
        throw 'Installer unexpectedly ignored registry access failure'
    } catch [System.UnauthorizedAccessException] {
        if (@(Get-ChildItem -LiteralPath $destination -Filter '*.ttf').Count -ne 0) {
            throw 'Installer copied fonts after registry access failure'
        }
    }
} else {
    . $Installer -SourceDirectory $source
    $expectedWrites = if ($Scenario -eq 'partial') { 1 } else { 16 }
    if ($script:writes -ne $expectedWrites -or [DotfilesFontNative]::Loads -ne $expectedWrites) {
        throw "Expected $expectedWrites registrations/loads; got $script:writes / $([DotfilesFontNative]::Loads)"
    }
    if ($script:registrations.Count -ne 17 -or $script:registrations['Unrelated Font (TrueType)'] -ne 'keep.ttf') {
        throw 'Missing managed fonts or unrelated registry value was changed'
    }
    foreach ($style in $styles) {
        $file = Join-Path $destination "JetBrainsMonoNerdFontMono-$style.ttf"
        $label = ($style -creplace 'Italic$', ' Italic').Trim()
        if (!(Test-Path -LiteralPath $file -PathType Leaf) -or
            $script:registrations["JetBrainsMono Nerd Font Mono $label (TrueType)"] -ne $file) {
            throw "Font was not copied/registered: $style"
        }
    }
    . $Installer -SourceDirectory $source
    if ($script:writes -ne $expectedWrites -or [DotfilesFontNative]::Loads -ne $expectedWrites) {
        throw 'Repeat install changed an already registered font'
    }
}
Write-Output "Windows font fixture passed: $Scenario"
