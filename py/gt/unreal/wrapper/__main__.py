
"""Command for gt.unreal.wrapper"""
import argparse
import logging
import sys

import envoy

from . import _initialize as unreal


log = logging.getLogger(__name__)


# Parse command line arguments before setting up logging
parser = argparse.ArgumentParser(description='Unreal Engine Wrapper')
parser.add_argument('--debug', action='store_true', 
                    help='Enable debug logging')
parser.add_argument('--version', "-v", type=str, default=None,
                    help='Specify Unreal Engine version (e.g. "5.5")')
parser.add_argument('args', nargs='*', 
                    help='Additional arguments to pass to Unreal Editor')

args, unknown_args = parser.parse_known_args()

# Set up logging based on debug flag
log_level = logging.DEBUG if args.debug else logging.INFO
logging.basicConfig(level=log_level)


log.info("Running Unreal Wrapper...")


# Resolve the executable path
unreal_exe = unreal.resolveUnrealExe(version=args.version)

if unreal_exe is None or not unreal_exe.exists():
    log.error(f"Unable to find executable for Unreal Editor at: {unreal_exe}")
    raise RuntimeError("Unable to find application...")


# # Check DX Version
# if not unreal.isDxCurrent():
#     log.info("DirectX needs to be updated. Running setup...")
#     proc = envoy.proc.spawn(["unreal-setup"],
#                          inheritenv=False,
#                          stdout=envoy.proc.PIPE,
#                          stderr=envoy.proc.STDOUT)
#     stdout, _ = proc.communicate()
#     print(stdout)
#     result = proc.returncode

#     if result:
#         log.error("Error running unreal-setup...")
#         raise RuntimeError("unreal-setup failed")
    
#     log.info("DirectX updated successfully.")


# Update registry for project compatibility
if not unreal.isBuildRegistered(version=args.version):
    log.info("Unreal Editor version not registered for project compatibility. Processing...")
    
    # Remove any currently registered builds. Unreal seems to only allow one here.
    unreal.removeRegisteredBuilds()
    
    # Register the current build
    unreal.registerBuild(version=args.version)



# Build the command line for Unreal Editor using parsed args
user_args = args.args + unknown_args

unreal_cmd = [str(unreal_exe)]

# Add any user-provided arguments
if user_args:
    log.debug(f"Passing user arguments to Unreal Editor: {' '.join(user_args)}")
    unreal_cmd.extend(user_args)
else:
    log.debug("No additional arguments provided")

log.info("Launching Unreal Editor...")
log.debug(f"Command: {' '.join(['envoy'] + unreal_cmd)}")

# Pre-build the UnrealEditor environment so we can inspect it before spawning.
# This also avoids a second bundle-discovery pass inside proc.spawn().
ue_env = envoy.proc.Environment(unreal_cmd[0], env_override='UnrealEditor')
built_env = ue_env.build()
log.debug("UE_PYTHONPATH: %s", built_env.get('UE_PYTHONPATH', '<NOT SET>'))
log.debug("PYTHONPATH:    %s", built_env.get('PYTHONPATH', '<NOT SET>'))

# Launch the application (reuses the already-built environment)
log.info("cmd: %s", ' '.join(unreal_cmd))
proc = ue_env.spawn(
    unreal_cmd[1:],
    stdout=envoy.proc.PIPE,
    stderr=envoy.proc.PIPE,
    creationflags=0,  # override envoy's CREATE_NO_WINDOW so output flows through
)
proc.wait()

if proc.returncode:
    log.error("Unreal Editor exited with error code: %d", proc.returncode)
    sys.exit(proc.returncode)
