@echo off

@REM set UE_BIN="D:\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
echo "UE_BIN: %UE_BIN%"
if not exist %UE_BIN% (
    echo Unreal Editor executable not found in %UE_BIN%. Please check the path and try again.
    goto :eof
)

echo Setting up environment variables for Unreal Engine...

@REM if defined UE_PYTHONPATH (
@REM     set UE_PYTHONPATH=%UE_PYTHONPATH%;%PYTHONPATH%
@REM ) else (
@REM     set UE_PYTHONPATH=%PYTHONPATH%
@REM )

echo "UE_PYTHONPATH: %UE_PYTHONPATH%"


start "" %UE_BIN%
