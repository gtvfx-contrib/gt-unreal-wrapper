@echo off

set "UE_BIN=D:/Epic Games/UE_5.4/Engine/Binaries/Win64/UnrealEditor.exe"

if not exist "%UE_BIN%" (
    echo Unreal Editor executable not found at %UE_BIN%. Please check the path and try again.
    goto :eof
)

echo Launching Unreal Editor...
"%UE_BIN%" %*
