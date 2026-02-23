"""Initialization module for the Unreal Engine wrapper."""

__all__ = [
    "getRegisteredBuilds",
    "getBuildPath", 
    "listBuildIds",
    "registerBuild",
    "registerBuildWithPath",
    "removeRegisteredBuilds",
    "getDxInstaller",
    "isDxCurrent",
    "isBuildRegistered",
    "UNREAL_BUILDS_PATH",
    "DX_REG_PATH",
    "UNREAL_ENV",
]

import os
import winreg

from pathlib import Path
from typing import Optional

import bl

from blizzard.logging import log

import t2.winreg

from t2.win32 import getFileVersion



UNREAL_BUILDS_PATH = (winreg.HKEY_CURRENT_USER, r"Software\Epic Games\Unreal Engine\Builds")
DX_REG_PATH = (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\DirectX")
UNREAL_ENV = bl.getEnvironment("UnrealEditor")



def getDxInstaller() -> Optional[os.PathLike]:
    """Get the path to the dxsetup.exe provided by the Unreal package.
    
    Searches for the DirectX installer (dxsetup.exe) in the Unreal Engine
    installation directory under BfdThirdParty/DirectXPrereq/.
    
    Returns:
        os.PathLike or None: Path to the DirectX installer if found, None otherwise
        
    Example:
        ```python
        dx_path = getDxInstaller()
        if dx_path:
            print(f"DirectX installer found at: {dx_path}")
        ```
        
    """
    dx_installer = (Path(UNREAL_ENV.get("UNREAL_LOCATION", "")) / 
                    "BfdThirdParty/DirectXPrereq/dxsetup.exe")

    if not dx_installer.exists():
        log.error(f"Did not find installer: {dx_installer}")
        return None

    return dx_installer


def isDxCurrent() -> bool:
    """Check if the installed DirectX version matches the packaged installer version.
    
    Compares the DirectX version registered in the Windows registry against
    the version of the dxsetup.exe installer provided with the Unreal package.
    
    Returns:
        bool: True if the installed DirectX version is current or newer than 
              the packaged version, False otherwise
              
    Example:
        ```python
        if not isDxCurrent():
            print("DirectX needs to be updated")
            # Run DirectX installer
        ```
        
    """
    # Get the current DirectX version from the registry
    installed_ver = t2.winreg.getRegistryValue(DX_REG_PATH, "Version")
    
    if installed_ver is None:
        # We can already assume it's not current if it's not in the registry
        log.debug("DirectX not installed...")
        return False
    
    dxsetup = getDxInstaller()
    
    if dxsetup and installed_ver:
        pkg_ver = getFileVersion(dxsetup)
        log.debug(f"dxsetup installed version: {installed_ver}")
        log.debug(f"dxsetup package version: {pkg_ver}")
        return pkg_ver >= installed_ver
    
    return False


def isBuildRegistered(major_version: str=UNREAL_ENV.get('UNREAL_MAJOR_VERSION', ''),
                      minor_version: str=UNREAL_ENV.get('UNREAL_MINOR_VERSION', ''),
                      location: str=UNREAL_ENV.get('UNREAL_LOCATION', '')) -> bool:
    """Test if a build matching the major and minor version is registered.
    
    Checks the Windows registry to determine if an Unreal Engine build with
    the specified major and minor version numbers is already registered and
    points to the correct location.
    
    Args:
        major_version (str, optional): Major version number (e.g., "5"). 
                                     Defaults to UNREAL_MAJOR_VERSION environment variable.
        minor_version (str, optional): Minor version number (e.g., "3").
                                     Defaults to UNREAL_MINOR_VERSION environment variable.
        location (str, optional): Expected installation path.
                                Defaults to UNREAL_LOCATION environment variable.
    
    Returns:
        bool: True if the build is registered with the correct location, False otherwise
        
    Example:
        ```python
        if isBuildRegistered("5", "3", "C:/UnrealEngine/5.3"):
            print("Unreal Engine 5.3 is registered at the correct location")
        ```
        
    """
    version_str = f"{major_version}.{minor_version}"
    
    # Check if the build ID exists
    registered_builds = getRegisteredBuilds()
    if not registered_builds:
        return False
    
    # Check if the version string (registry key name) exists
    if version_str not in registered_builds:
        return False
    
    # Check if the location matches
    registered_location = registered_builds[version_str]
    
    # Normalize paths for comparison (convert both to forward slashes)
    if isinstance(location, str):
        normalized_location = location.replace('\\', '/')
    else:
        normalized_location = str(location).replace('\\', '/')
        
    if isinstance(registered_location, str):
        normalized_registered = registered_location.replace('\\', '/')
    else:
        normalized_registered = str(registered_location).replace('\\', '/')
    
    return normalized_location == normalized_registered


def getRegisteredBuilds() -> Optional[dict[str, str]]:
    """Get all registered Unreal Engine builds from the Windows registry.
    
    Retrieves a dictionary mapping build IDs (version strings like "5.3") 
    to their installation paths.
    
    Returns:
        dict[str, str] or None: Dictionary mapping build IDs to installation paths,
                               or None if no builds are registered or registry access fails
                               
    Example:
        ```python
        builds = getRegisteredBuilds()
        if builds:
            for build_id, path in builds.items():
                print(f"Unreal Engine {build_id}: {path}")
        ```
        
    """
    return t2.winreg.getRegistryValues(UNREAL_BUILDS_PATH)


def getBuildPath(build_id: str) -> Optional[str]:
    """Get the installation path for a specific Unreal Engine build.
    
    Args:
        build_id (str): The build ID to look up (e.g., "5.3")
        
    Returns:
        str or None: Installation path for the build, or None if not found
        
    Example:
        ```python
        path = getBuildPath("5.3")
        if path:
            print(f"Unreal Engine 5.3 is installed at: {path}")
        ```
        
    """
    return t2.winreg.getRegistryValue(UNREAL_BUILDS_PATH, build_id)


def listBuildIds() -> Optional[list[str]]:
    """Get list of all registered Unreal Engine build IDs.
    
    Returns a list of version strings for all Unreal Engine builds
    that are currently registered in the Windows registry.
    
    Returns:
        list[str] or None: List of build IDs (e.g., ["5.2", "5.3"]), 
                          or None if no builds are registered
                          
    Example:
        ```python
        build_ids = listBuildIds()
        if build_ids:
            print("Registered Unreal Engine versions:", ", ".join(build_ids))
        ```
        
    """
    builds = t2.winreg.getRegistryValues(UNREAL_BUILDS_PATH)
    return list(builds.keys()) if builds else None


def registerBuild() -> bool:
    """Register the current Unreal Engine build in the registry.
    
    Uses environment variables UNREAL_MAJOR_VERSION, UNREAL_MINOR_VERSION,
    and UNREAL_LOCATION.
    
    Returns:
        True if registration was successful, False otherwise
        
    """
    # Get environment variables
    major_version = UNREAL_ENV.get('UNREAL_MAJOR_VERSION')
    minor_version = UNREAL_ENV.get('UNREAL_MINOR_VERSION')
    unreal_location = UNREAL_ENV.get('UNREAL_LOCATION')

    # Validate environment variables
    if not major_version:
        log.error("UNREAL_MAJOR_VERSION environment variable not set")
        return False
    
    if not minor_version:
        log.error("UNREAL_MINOR_VERSION environment variable not set")
        return False
    
    if not unreal_location:
        log.error("UNREAL_LOCATION environment variable not set")
        return False
    
    # Validate that the Unreal location exists
    if not os.path.exists(unreal_location):
        log.warning(f"Unreal Engine location does not exist: {unreal_location}")
    
    # Create the build ID key
    build_id = f"{major_version}.{minor_version}"
    
    # Register the build
    success = t2.winreg.setRegistryValueString(UNREAL_BUILDS_PATH,
                                               build_id,
                                               unreal_location.replace('\\', '/'))
    
    if success:
        log.info(f"Successfully registered Unreal Engine {build_id} at {unreal_location}")
    else:
        log.error(f"Failed to register Unreal Engine {build_id}")
    
    return success


def registerBuildWithPath(major_version: str, minor_version: str, location: str) -> bool:
    """Register an Unreal Engine build in the registry with explicit parameters.
    
    Args:
        major_version: Major version number (e.g., "5")
        minor_version: Minor version number (e.g., "3")
        location: Path to the Unreal Engine installation
        
    Returns:
        True if registration was successful, False otherwise
        
    """
    # Validate that the location exists
    if not os.path.exists(location):
        log.warning(f"Unreal Engine location does not exist: {location}")
    
    # Create the build ID key
    build_id = f"{major_version}.{minor_version}"
    
    # Register the build
    success = t2.winreg.setRegistryValueString(UNREAL_BUILDS_PATH, build_id, location)
    
    if success:
        log.info(f"Successfully registered Unreal Engine {build_id} at {location}")
    else:
        log.error(f"Failed to register Unreal Engine {build_id}")
    
    return success


def removeRegisteredBuilds() -> bool:
    """Remove registered Unreal Engine builds that match the current UNREAL_LOCATION.
    
    Deletes registry values at UNREAL_BUILDS_PATH that point to the same location
    as the current UNREAL_LOCATION environment variable. This allows cleaning up
    conflicting entries without affecting other Unreal Engine installations.
    
    Returns:
        bool: True if removal was successful, False otherwise
        
    Example:
        ```python
        if removeRegisteredBuilds():
            print("Conflicting builds have been removed")
        ```
        
    """
    try:
        # Get current Unreal location from environment
        current_location = UNREAL_ENV.get('UNREAL_LOCATION', '')
        
        if not current_location:
            log.warning("UNREAL_LOCATION environment variable not set, "
                        "cannot determine which builds to remove")
            return False
        
        # Normalize current location for comparison
        normalized_current = current_location.replace('\\', '/')
        
        # Get all current build registrations
        builds = t2.winreg.getRegistryValues(UNREAL_BUILDS_PATH)
        
        if not builds:
            log.debug("No registered builds found to remove")
            return True
        
        # Remove only builds that match the current location
        removed_count = 0
        for build_id, build_location in builds.items():
            # Normalize registered location for comparison
            if isinstance(build_location, str):
                normalized_registered = build_location.replace('\\', '/')
            else:
                normalized_registered = str(build_location).replace('\\', '/')
                
            # Only remove if locations match
            if normalized_registered == normalized_current:
                if t2.winreg.deleteRegistryValue(UNREAL_BUILDS_PATH, build_id):
                    log.debug(f"Removed build registration: {build_id} "
                              f"(matched location: {normalized_current})")
                    removed_count += 1
                else:
                    log.warning(f"Failed to remove build registration: {build_id}")
            else:
                log.debug(f"Skipping build {build_id} with different "
                          f"location: {normalized_registered}")
        
        if removed_count > 0:
            log.info(f"Successfully removed {removed_count} registered Unreal Engine "
                     f"builds matching {normalized_current}")
        else:
            log.debug(f"No build registrations matching {normalized_current} needed removal")
            
        return True
        
    except (OSError, PermissionError) as e:
        log.error(f"Failed to remove registered builds due to registry access error: {e}")
        return False
    except (TypeError, ValueError) as e:
        log.error(f"Failed to remove registered builds due to data error: {e}")
        return False
