<#
.SYNOPSIS
    Link an IngeTrazo extension from this repo into IngeTrazo's user plugins
    folder for live development, or remove/list existing links.

.DESCRIPTION
    IngeTrazo scans its user plugins folder (%APPDATA%\ingetrazo\plugins\ on
    Windows) at startup for either:
      - loose "<name>.py" files, or
      - "<name>\__init__.py" packages.
    It does NOT scan a folder containing "<name>\<name>.py" (the convention
    used by extensions in this repo, e.g.
    extensions\standalone-3d-html-viewer\).

    This script resolves an extension by name under this repo's
    extensions\ folder and creates a symbolic link (falling back to a
    directory junction, or a hard link for a single file, when symlinks
    require elevated permissions) so edits made in this repo are picked up
    the next time IngeTrazo starts.

    Resolution order for -Name <Ext>, under "<repo>\extensions\":
      1. "extensions\<Ext>.py"          - a loose single-file extension.
      2. "extensions\<Ext>\__init__.py" - a true package folder; the whole
                                           folder is linked.
      3. "extensions\<Ext>\<Ext>.py"    - this repo's folder convention
                                           (folder + README.md + same-named
                                           .py); only the inner .py file is
                                           linked, as "<Ext>.py".

.PARAMETER Name
    The extension to link, matching a file or folder under this repo's
    extensions\ folder (e.g. "standalone-3d-html-viewer"). Required unless
    -List is used.

.PARAMETER Unlink
    Remove the existing link for -Name from the plugins folder. Only
    removes an entry that is actually a symlink/junction/hard link (never a
    real, non-linked extension that happens to share the name).

.PARAMETER List
    Show every entry currently in the plugins folder, whether it is a link
    created by this script, and whether it resolves back into this repo.

.EXAMPLE
    scripts\dev-link.ps1 -Name standalone-3d-html-viewer

.EXAMPLE
    scripts\dev-link.ps1 -Name standalone-3d-html-viewer -Unlink

.EXAMPLE
    scripts\dev-link.ps1 -List
#>
[CmdletBinding(DefaultParameterSetName = 'Link')]
param(
    [Parameter(ParameterSetName = 'Link', Position = 0, Mandatory = $true)]
    [Parameter(ParameterSetName = 'Unlink', Mandatory = $true)]
    [string]$Name,

    [Parameter(ParameterSetName = 'Unlink', Mandatory = $true)]
    [switch]$Unlink,

    [Parameter(ParameterSetName = 'List', Mandatory = $true)]
    [switch]$List
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    return $root.TrimEnd('\')
}

function Get-PluginsDir {
    $appData = $env:APPDATA
    if (-not $appData) {
        throw "Cannot determine %APPDATA%; this script targets Windows."
    }
    return Join-Path $appData 'ingetrazo\plugins'
}

function Test-ReparsePoint {
    param([System.IO.FileSystemInfo]$Item)
    return [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Test-HardLinkToRepo {
    param([string]$Path, [string]$RepoRoot)
    # A hard-linked file shares the same file ID as its repo source; compare
    # via fsutil since PowerShell has no direct hard-link enumeration.
    try {
        $fsutilOut = fsutil hardlink list $Path 2>$null
        if (-not $fsutilOut) { return $false }
        foreach ($line in $fsutilOut) {
            $full = Join-Path (Split-Path -Qualifier $Path) $line
            if ($full -like "$RepoRoot\*") { return $true }
        }
    } catch {
        return $false
    }
    return $false
}

function Get-ExtensionsDir {
    param([string]$RepoRoot)
    return Join-Path $RepoRoot 'extensions'
}

function Resolve-Extension {
    param([string]$RepoRoot, [string]$ExtName)

    $extensionsDir = Get-ExtensionsDir -RepoRoot $RepoRoot

    $looseFile = Join-Path $extensionsDir "$ExtName.py"
    if (Test-Path -LiteralPath $looseFile -PathType Leaf) {
        return [pscustomobject]@{
            Kind       = 'file'
            SourcePath = (Resolve-Path $looseFile).Path
            LinkName   = "$ExtName.py"
        }
    }

    $folder = Join-Path $extensionsDir $ExtName
    if (Test-Path -LiteralPath $folder -PathType Container) {
        $initPy = Join-Path $folder '__init__.py'
        if (Test-Path -LiteralPath $initPy -PathType Leaf) {
            return [pscustomobject]@{
                Kind       = 'package-folder'
                SourcePath = (Resolve-Path $folder).Path
                LinkName   = $ExtName
            }
        }

        $innerPy = Join-Path $folder "$ExtName.py"
        if (Test-Path -LiteralPath $innerPy -PathType Leaf) {
            return [pscustomobject]@{
                Kind       = 'folder-convention'
                SourcePath = (Resolve-Path $innerPy).Path
                LinkName   = "$ExtName.py"
            }
        }

        throw ("Found folder '$folder' but it has neither '__init__.py' " +
               "nor '$ExtName.py'; cannot determine its entry point.")
    }

    throw ("Could not find extension '$ExtName'. Looked for:`n" +
           "  - $looseFile`n" +
           "  - $folder\__init__.py`n" +
           "  - $folder\$ExtName.py")
}

function New-DevLink {
    param([string]$SourcePath, [string]$LinkPath, [string]$Kind)

    if (Test-Path -LiteralPath $LinkPath) {
        $existing = Get-Item -LiteralPath $LinkPath -Force
        if (Test-ReparsePoint $existing) {
            Remove-Item -LiteralPath $LinkPath -Force -Recurse:($existing.PSIsContainer)
        } else {
            throw ("'$LinkPath' already exists and is not a link created by " +
                   "this script. Remove it manually if you want to replace it.")
        }
    }

    $isDir = $Kind -eq 'package-folder'
    $itemType = if ($isDir) { 'SymbolicLink' } else { 'SymbolicLink' }

    try {
        New-Item -ItemType $itemType -Path $LinkPath -Target $SourcePath -ErrorAction Stop | Out-Null
        return 'symlink'
    } catch {
        Write-Warning ("Symbolic link creation failed (likely missing " +
                       "elevated permissions or Developer Mode): $($_.Exception.Message)")
    }

    if ($isDir) {
        try {
            New-Item -ItemType Junction -Path $LinkPath -Target $SourcePath -ErrorAction Stop | Out-Null
            return 'junction'
        } catch {
            throw ("Could not create a symlink or a junction for '$LinkPath'. " +
                   "Enable Windows Developer Mode (Settings > Update & Security > " +
                   "For developers) or re-run this script from an elevated " +
                   "PowerShell prompt. Underlying error: $($_.Exception.Message)")
        }
    } else {
        try {
            cmd /c mklink /H "`"$LinkPath`"" "`"$SourcePath`"" | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "mklink /H exited with code $LASTEXITCODE" }
            return 'hardlink'
        } catch {
            throw ("Could not create a symlink or a hard link for '$LinkPath'. " +
                   "Enable Windows Developer Mode (Settings > Update & Security > " +
                   "For developers) or re-run this script from an elevated " +
                   "PowerShell prompt. Underlying error: $($_.Exception.Message)")
        }
    }
}

function Remove-DevLink {
    param([string]$RepoRoot, [string]$ExtName, [string]$PluginsDir)

    $candidates = @(
        (Join-Path $PluginsDir "$ExtName.py"),
        (Join-Path $PluginsDir $ExtName)
    )

    $removed = $false
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        $item = Get-Item -LiteralPath $candidate -Force
        $isLink = Test-ReparsePoint $item
        $isHardLink = (-not $isLink) -and (-not $item.PSIsContainer) -and (Test-HardLinkToRepo $candidate $RepoRoot)

        if ($isLink -or $isHardLink) {
            Remove-Item -LiteralPath $candidate -Force -Recurse:($item.PSIsContainer)
            Write-Host "Removed link: $candidate"
            $removed = $true
        } else {
            Write-Warning ("'$candidate' exists but is not a link created by " +
                           "this script; leaving it in place.")
        }
    }

    if (-not $removed) {
        Write-Warning "No link found for '$ExtName' in $PluginsDir."
    }
}

function Show-LinkedExtensions {
    param([string]$RepoRoot, [string]$PluginsDir)

    if (-not (Test-Path -LiteralPath $PluginsDir)) {
        Write-Host "Plugins folder does not exist yet: $PluginsDir"
        return
    }

    $entries = Get-ChildItem -LiteralPath $PluginsDir -Force
    if (-not $entries) {
        Write-Host "No extensions installed in $PluginsDir"
        return
    }

    foreach ($entry in $entries) {
        $isLink = Test-ReparsePoint $entry
        $pointsToRepo = $false
        $target = $null

        if ($isLink) {
            $target = (Get-Item -LiteralPath $entry.FullName -Force).Target
            if ($target) {
                $resolvedTarget = $target
                if (-not [System.IO.Path]::IsPathRooted($resolvedTarget)) {
                    $resolvedTarget = Join-Path $PluginsDir $resolvedTarget
                }
                $pointsToRepo = $resolvedTarget -like "$RepoRoot\*" -or $resolvedTarget -eq $RepoRoot
            }
        } elseif (-not $entry.PSIsContainer) {
            $pointsToRepo = Test-HardLinkToRepo $entry.FullName $RepoRoot
        }

        $status = if ($isLink -and $pointsToRepo) {
            "linked -> this repo ($target)"
        } elseif ($isLink) {
            "linked -> $target"
        } elseif ($pointsToRepo) {
            "hard-linked -> this repo"
        } else {
            "installed copy (not linked)"
        }

        Write-Host ("{0,-40} {1}" -f $entry.Name, $status)
    }
}

# ---- Main -------------------------------------------------------------

$repoRoot = Get-RepoRoot
$pluginsDir = Get-PluginsDir

if ($List) {
    Show-LinkedExtensions -RepoRoot $repoRoot -PluginsDir $pluginsDir
    return
}

if (-not (Test-Path -LiteralPath $pluginsDir)) {
    New-Item -ItemType Directory -Path $pluginsDir -Force | Out-Null
}

if ($Unlink) {
    Remove-DevLink -RepoRoot $repoRoot -ExtName $Name -PluginsDir $pluginsDir
    return
}

$ext = Resolve-Extension -RepoRoot $repoRoot -ExtName $Name
$linkPath = Join-Path $pluginsDir $ext.LinkName

$method = New-DevLink -SourcePath $ext.SourcePath -LinkPath $linkPath -Kind $ext.Kind

Write-Host "Linked '$Name' ($($ext.Kind)) into $linkPath using a $method."
Write-Host "Source: $($ext.SourcePath)"
