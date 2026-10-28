@echo off
rem Lanceur double-cliquable de install-claude.ps1 (contourne la politique d'execution pour ce seul script).
rem Arguments transmis tels quels, ex. : install-claude.cmd -RepoPath D:\family_abm -CopySpecs -IncludeProjectDocs
setlocal
where pwsh >nul 2>nul && (set "PS=pwsh") || (set "PS=powershell")
%PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-claude.ps1" %*
set "RC=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RC%
