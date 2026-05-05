@echo off
SETLOCAL

REM User settings
SET USER_NAME=Leonardo Fonseca
SET USER_EMAIL=leonardofonsecasilva@hotmail.com

REM Local Git configuration
git config user.name "%USER_NAME%"
git config user.email "%USER_EMAIL%"

REM Display local configurations
echo Local information:
git config --local user.name
git config --local user.email

echo.

REM Display global configurations
echo Global information:
git config --global user.name
git config --global user.email

ENDLOCAL
pause