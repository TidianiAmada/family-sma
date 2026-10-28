<#
.SYNOPSIS
    Installe le dispositif Claude Code de family_abm (personas, skills, commandes, CLAUDE.md)
    depuis le dossier specs vers un depot.

.DESCRIPTION
    Copie, depuis le dossier qui contient ce script (le dossier specs) :
      claude-agents\*.md      -> <Depot>\.claude\agents\
      claude-skills\<nom>\*   -> <Depot>\.claude\skills\<nom>\
      claude-commands\*.md    -> <Depot>\.claude\commands\
      CLAUDE.md               -> <Depot>\CLAUDE.md                  (protege)
      odd\*.md, docs\*.md     -> <Depot>\odd\, <Depot>\docs\        (avec -IncludeProjectDocs, proteges)
      tout le dossier specs   -> <Depot>\specs\                     (avec -CopySpecs, si le depot est ailleurs)

    Fichiers geres (agents, skills, commandes) : remplaces s'ils ont change ; l'ancienne version est sauvegardee.
    Fichiers proteges (CLAUDE.md, odd, docs, specs) : crees s'ils n'existent pas ; jamais ecrases sans -Force,
    car l'auteur les modifie (l'ODD devient le texte du memoire).

    Sauvegardes : <Depot>\.claude-backup\<horodatage>\... (ajoute a .gitignore).
    Manifeste   : <Depot>\.claude\.install-manifest.json (sert a -Prune).

.PARAMETER RepoPath
    Racine du depot cible. Par defaut : le dossier parent du dossier specs. Cree s'il n'existe pas.

.PARAMETER IncludeProjectDocs
    Copie aussi odd\ et docs\ dans le depot (sans ecraser l'existant, sauf -Force).

.PARAMETER CopySpecs
    Copie le dossier specs dans <Depot>\specs (utile quand le depot n'est pas le parent de specs).

.PARAMETER Force
    Autorise l'ecrasement des fichiers proteges qui different (avec sauvegarde).

.PARAMETER Prune
    Supprime (apres sauvegarde) les agents, skills et commandes installes precedemment
    qui n'existent plus dans le dossier specs.

.PARAMETER NoBackup
    Ne sauvegarde pas les fichiers remplaces ou supprimes.

.EXAMPLE
    .\install-claude.ps1
    Installe dans le dossier parent de specs (ex. D:\family-sma).

.EXAMPLE
    .\install-claude.ps1 -RepoPath D:\family_abm -CopySpecs -IncludeProjectDocs

.EXAMPLE
    .\install-claude.ps1 -WhatIf
    Affiche ce qui serait fait, sans rien ecrire.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoPath,
    [switch]$IncludeProjectDocs,
    [switch]$CopySpecs,
    [switch]$Force,
    [switch]$Prune,
    [switch]$NoBackup
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- chemins
$SpecsDir = $PSScriptRoot
if (-not $SpecsDir) { $SpecsDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$SpecsDir = (Resolve-Path -LiteralPath $SpecsDir).Path.TrimEnd('\', '/')

if (-not $RepoPath) { $RepoPath = Split-Path -Parent $SpecsDir }
if (-not (Test-Path -LiteralPath $RepoPath)) {
    if ($PSCmdlet.ShouldProcess($RepoPath, 'Creer le dossier du depot')) {
        New-Item -ItemType Directory -Path $RepoPath -Force | Out-Null
    }
}
if (Test-Path -LiteralPath $RepoPath) {
    $RepoPath = (Resolve-Path -LiteralPath $RepoPath).Path.TrimEnd('\', '/')
}

$ClaudeDir   = Join-Path $RepoPath '.claude'
$Timestamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupRoot  = Join-Path (Join-Path $RepoPath '.claude-backup') $Timestamp
$ManifestPath = Join-Path $ClaudeDir '.install-manifest.json'

# ---------------------------------------------------------------- verification de la source
$required = @('CLAUDE.md', 'claude-agents', 'claude-skills', 'claude-commands')
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $SpecsDir $_)) })
if ($missing.Count -gt 0) {
    throw "Dossier specs incomplet ($SpecsDir) : il manque $($missing -join ', '). Lance le script depuis le dossier specs."
}

# ---------------------------------------------------------------- etat
$Stats = [ordered]@{ Crees = 0; MisAJour = 0; Identiques = 0; Proteges = 0; Supprimes = 0; Sauvegardes = 0; Avertissements = 0 }
$Installed = New-Object System.Collections.Generic.List[string]   # chemins relatifs au depot (fichiers geres)
$Report = New-Object System.Collections.Generic.List[object]

function Get-RelativePath([string]$Base, [string]$Full) {
    $b = $Base.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if ($Full.StartsWith($b, [StringComparison]::OrdinalIgnoreCase)) { return $Full.Substring($b.Length) }
    return $Full
}

function Test-SameContent([string]$A, [string]$B) {
    if (-not (Test-Path -LiteralPath $B)) { return $false }
    return (Get-FileHash -LiteralPath $A -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $B -Algorithm SHA256).Hash
}

function Backup-File([string]$Path) {
    if ($NoBackup -or -not (Test-Path -LiteralPath $Path)) { return }
    $rel = Get-RelativePath $RepoPath $Path
    $dest = Join-Path $BackupRoot $rel
    if ($PSCmdlet.ShouldProcess($Path, "Sauvegarder vers $dest")) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
        Copy-Item -LiteralPath $Path -Destination $dest -Force
        $Stats.Sauvegardes++
    }
}

function Add-Report([string]$Action, [string]$Path) {
    $Report.Add([pscustomobject]@{ Action = $Action; Fichier = (Get-RelativePath $RepoPath $Path) })
}

# Policy 'Managed'  : remplace si different (sauvegarde)
# Policy 'Protected': cree si absent ; si different, ecrase seulement avec -Force (sauvegarde)
function Install-File([string]$Source, [string]$Destination, [ValidateSet('Managed', 'Protected')][string]$Policy) {
    $exists = Test-Path -LiteralPath $Destination
    if ($exists -and (Test-SameContent $Source $Destination)) {
        $Stats.Identiques++
        if ($Policy -eq 'Managed') { $Installed.Add((Get-RelativePath $RepoPath $Destination)) }
        return
    }
    if ($exists -and $Policy -eq 'Protected' -and -not $Force) {
        $Stats.Proteges++
        Add-Report 'protege (different, non ecrase ; -Force pour remplacer)' $Destination
        return
    }
    if ($PSCmdlet.ShouldProcess($Destination, $(if ($exists) { 'Remplacer' } else { 'Creer' }))) {
        if ($exists) { Backup-File $Destination }
        New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        if ($exists) { $Stats.MisAJour++; Add-Report 'mis a jour' $Destination }
        else { $Stats.Crees++; Add-Report 'cree' $Destination }
    }
    if ($Policy -eq 'Managed') { $Installed.Add((Get-RelativePath $RepoPath $Destination)) }
}

function Install-Tree([string]$SourceDir, [string]$DestDir, [string]$Filter, [string]$Policy) {
    if (-not (Test-Path -LiteralPath $SourceDir)) { return }
    Get-ChildItem -LiteralPath $SourceDir -Recurse -File -Filter $Filter | ForEach-Object {
        $rel = Get-RelativePath $SourceDir $_.FullName
        Install-File $_.FullName (Join-Path $DestDir $rel) $Policy
    }
}

function Test-Frontmatter([string]$Path, [string[]]$Keys) {
    $head = @(Get-Content -LiteralPath $Path -TotalCount 15 -Encoding UTF8)
    if ($head.Count -eq 0 -or $head[0].Trim() -ne '---') {
        Write-Warning "Frontmatter YAML absent : $Path"; $Stats.Avertissements++; return
    }
    foreach ($k in $Keys) {
        if (-not ($head | Where-Object { $_ -match "^\s*$k\s*:" })) {
            Write-Warning "Cle '$k' absente du frontmatter : $Path"; $Stats.Avertissements++
        }
    }
}

# ---------------------------------------------------------------- validation des sources
Get-ChildItem -LiteralPath (Join-Path $SpecsDir 'claude-agents') -Filter *.md -File | ForEach-Object { Test-Frontmatter $_.FullName @('name', 'description') }
Get-ChildItem -LiteralPath (Join-Path $SpecsDir 'claude-skills') -Directory | ForEach-Object {
    $skill = Join-Path $_.FullName 'SKILL.md'
    if (-not (Test-Path -LiteralPath $skill)) { Write-Warning "SKILL.md absent : $($_.FullName)"; $Stats.Avertissements++ }
    else { Test-Frontmatter $skill @('name', 'description') }
}
Get-ChildItem -LiteralPath (Join-Path $SpecsDir 'claude-commands') -Filter *.md -File | ForEach-Object { Test-Frontmatter $_.FullName @('description') }

# ---------------------------------------------------------------- installation
Write-Host "Source : $SpecsDir" -ForegroundColor Cyan
Write-Host "Depot  : $RepoPath" -ForegroundColor Cyan

Install-Tree (Join-Path $SpecsDir 'claude-agents')   (Join-Path $ClaudeDir 'agents')   '*.md' 'Managed'
Install-Tree (Join-Path $SpecsDir 'claude-skills')   (Join-Path $ClaudeDir 'skills')   '*'    'Managed'
Install-Tree (Join-Path $SpecsDir 'claude-commands') (Join-Path $ClaudeDir 'commands') '*.md' 'Managed'
Install-File (Join-Path $SpecsDir 'CLAUDE.md') (Join-Path $RepoPath 'CLAUDE.md') 'Protected'

if ($IncludeProjectDocs) {
    Install-Tree (Join-Path $SpecsDir 'odd')  (Join-Path $RepoPath 'odd')  '*.md' 'Protected'
    Install-Tree (Join-Path $SpecsDir 'docs') (Join-Path $RepoPath 'docs') '*.md' 'Protected'
}

$repoSpecs = Join-Path $RepoPath 'specs'
if ($CopySpecs) {
    if ($repoSpecs.TrimEnd('\', '/') -ieq $SpecsDir) {
        Write-Host "-CopySpecs ignore : le dossier specs est deja dans le depot." -ForegroundColor DarkGray
    } else {
        Install-Tree $SpecsDir $repoSpecs '*' 'Protected'
    }
}

# ---------------------------------------------------------------- nettoyage (-Prune)
$previous = @()
if (Test-Path -LiteralPath $ManifestPath) {
    try { $previous = @((Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json).files) } catch { $previous = @() }
}
$obsolete = @($previous | Where-Object { $_ -and ($Installed -notcontains $_) })
if ($obsolete.Count -gt 0) {
    if ($Prune) {
        foreach ($rel in $obsolete) {
            $p = Join-Path $RepoPath $rel
            if ((Test-Path -LiteralPath $p) -and $PSCmdlet.ShouldProcess($p, 'Supprimer (obsolete)')) {
                Backup-File $p
                Remove-Item -LiteralPath $p -Force
                $Stats.Supprimes++
                Add-Report 'supprime (obsolete)' $p
                $dir = Split-Path -Parent $p
                if ((Test-Path -LiteralPath $dir) -and -not (Get-ChildItem -LiteralPath $dir -Force)) { Remove-Item -LiteralPath $dir -Force }
            }
        }
    } else {
        Write-Host "$($obsolete.Count) fichier(s) installe(s) precedemment ne sont plus dans specs (relancer avec -Prune pour les retirer) :" -ForegroundColor Yellow
        $obsolete | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    }
}

# ---------------------------------------------------------------- manifeste et .gitignore
if ((Test-Path -LiteralPath $RepoPath) -and $PSCmdlet.ShouldProcess($ManifestPath, 'Ecrire le manifeste')) {
    New-Item -ItemType Directory -Path $ClaudeDir -Force | Out-Null
    $manifest = [ordered]@{
        installed_at = (Get-Date).ToString('s')
        source       = $SpecsDir
        files        = @($Installed | Sort-Object -Unique)
    }
    $json = $manifest | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText($ManifestPath, $json, (New-Object System.Text.UTF8Encoding($false)))
}

$gitignore = Join-Path $RepoPath '.gitignore'
$ignoreLine = '.claude-backup/'
$hasLine = (Test-Path -LiteralPath $gitignore) -and (Select-String -LiteralPath $gitignore -Pattern $ignoreLine -SimpleMatch -Quiet)
if (-not $hasLine -and (Test-Path -LiteralPath $RepoPath) -and $PSCmdlet.ShouldProcess($gitignore, "Ajouter '$ignoreLine'")) {
    # UTF-8 sans BOM : un BOM en tete de .gitignore casserait le premier motif
    $prefix = ''
    if (Test-Path -LiteralPath $gitignore) {
        $raw = [IO.File]::ReadAllText($gitignore)
        if ($raw.Length -gt 0 -and -not $raw.EndsWith("`n")) { $prefix = [Environment]::NewLine }
    }
    [IO.File]::AppendAllText($gitignore, $prefix + $ignoreLine + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))
}

# ---------------------------------------------------------------- resume
Write-Host ''
if ($Report.Count -gt 0) { $Report | Sort-Object Fichier | Format-Table -AutoSize | Out-String -Width 200 | Write-Host }
$Stats.GetEnumerator() | ForEach-Object { '{0,-15} {1}' -f $_.Key, $_.Value } | Write-Host
if ($Stats.Sauvegardes -gt 0) { Write-Host "Sauvegardes : $BackupRoot" -ForegroundColor DarkGray }

$nAgents   = @(Get-ChildItem -LiteralPath (Join-Path $ClaudeDir 'agents')   -Filter *.md -File -ErrorAction SilentlyContinue).Count
$nSkills   = @(Get-ChildItem -LiteralPath (Join-Path $ClaudeDir 'skills')   -Directory -ErrorAction SilentlyContinue).Count
$nCommands = @(Get-ChildItem -LiteralPath (Join-Path $ClaudeDir 'commands') -Filter *.md -File -ErrorAction SilentlyContinue).Count
Write-Host ''
Write-Host "Installe dans $ClaudeDir : $nAgents personas, $nSkills skills, $nCommands commandes." -ForegroundColor Green
Write-Host "Ensuite : ouvrir Claude Code dans $RepoPath, verifier avec /agents, puis /implement-ticket T-001." -ForegroundColor Green
if ($Stats.Avertissements -gt 0) { exit 2 }
exit 0
