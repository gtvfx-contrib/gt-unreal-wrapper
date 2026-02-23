# pylint: disable=C0103
# Team2 expects underscore-separated variable names
################################################################################
# THIS CODE IS PROPRIETARY PROPERTY OF BLIZZARD ENTERTAINMENT, INC.
# The contents of this file may not be disclosed, copied or duplicated in any
# form, in whole or in part, without the prior written permission of
# Blizzard Entertainment, Inc.
################################################################################
"""Command for t2.unreal.wrapper"""
import argparse
import os
import sys

import bl

from blizzard.logging import log, OutputHandler, INFO, DEBUG

from . import _initialize as unreal


# Parse command line arguments before setting up logging
parser = argparse.ArgumentParser(description='Unreal Engine Wrapper')
parser.add_argument('--debug', action='store_true', 
                    help='Enable debug logging')
parser.add_argument('args', nargs='*', 
                    help='Additional arguments to pass to Unreal Editor')

args, unknown_args = parser.parse_known_args()

# Set up logging based on debug flag
log_level = DEBUG if args.debug else INFO
OutputHandler(name=__name__, level=log_level)


log.info("Running Unreal Wrapper...")


# Resolve the executable path
unreal_exe = unreal.UNREAL_ENV.get("BFD_UE_EDITOR", "")

if not os.path.exists(unreal_exe):
    log.error(f"Unable to find executable for Unreal Editor at: {unreal_exe}")
    raise RuntimeError("Unable to find application...")


# Check DX Version
if not unreal.isDxCurrent():
    log.info("DirectX needs to be updated. Running setup...")
    proc = bl.proc.spawn(["unreal-setup"],
                         inheritenv=False,
                         stdout=bl.proc.PIPE,
                         stderr=bl.proc.STDOUT)
    stdout, _ = proc.communicate()
    print(stdout)
    result = proc.returncode

    if result:
        log.error("Error running unreal-setup...")
        raise RuntimeError("unreal-setup failed")
    
    log.info("DirectX updated successfully.")


# Update registry for project compatibility
if not unreal.isBuildRegistered():
    log.info("Unreal Editor version not registered for project compatibility. Processing...")
    
    # Remove any currently registered builds. Unreal seems to only allow one here.
    unreal.removeRegisteredBuilds()
    
    # Register the current build
    unreal.registerBuild()



# Build the command line for Unreal Editor using parsed args
user_args = args.args + unknown_args

unreal_cmd = ["-e=UnrealEditor", unreal_exe]

# Add any user-provided arguments
if user_args:
    log.debug(f"Passing user arguments to Unreal Editor: {' '.join(user_args)}")
    unreal_cmd.extend(user_args)
else:
    log.debug("No additional arguments provided")

log.info("Launching Unreal Editor...")
log.debug(f"Command: {' '.join(['bl'] + unreal_cmd)}")


# Launch the application
proc = bl.proc.spawn(unreal_cmd)
proc.communicate()

# Check return code and exit with error if needed
if proc.returncode:
    log.error(f"Unreal Editor exited with error code: {proc.returncode}")
    sys.exit(proc.returncode)
