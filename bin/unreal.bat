@echo off

if not exist "%UE_BIN%" (
    echo Unreal Editor executable not found at %UE_BIN%. Please check the path and try again.
    goto :eof
)

"%UE_BIN%" %*
