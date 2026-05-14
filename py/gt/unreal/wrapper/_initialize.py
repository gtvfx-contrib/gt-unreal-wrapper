
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
    "resolveUnrealPath",
    "resolveUnrealExe",
]

import json
import functools
import logging
import os
import re
import winreg
from pathlib import Path
from typing import Optional

import envoy

import gt.winreg
from gt.win32 import getFileVersion

log = logging.getLogger(__name__)



UNREAL_BUILDS_PATH = (winreg.HKEY_CURRENT_USER, r"Software\Epic Games\Unreal Engine\Builds")
DX_REG_PATH = (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\DirectX")
UNREAL_ENV = envoy.get_environment("UnrealEditor")



_EPIC_REGISTRY_BASE = (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\EpicGames\Unreal Engine")
_LAUNCHER_DAT = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData")) / "Epic" / "UnrealEngineLauncher" / "LauncherInstalled.dat"



def _sort_version_key(v: str) -> tuple:
    """Convert a version string like '5.7' into a sortable tuple of ints."""
    return tuple(int(p) for p in re.split(r'[^0-9]+', v) if p)


def _version_from_path(path: Path) -> Optional[str]:
    """Extract the Unreal Engine version string from an installation path.

    Matches the first ``MAJOR.MINOR`` pattern found in the final path component,
    so ``D:/Epic Games/UE_5.7`` → ``'5.7'`` and ``C:/UE/5.4`` → ``'5.4'``.

    Returns ``None`` if no version pattern is found.

    """
    m = re.search(r'(\d+\.\d+)', path.name)
    return m.group(1) if m else None


@functools.cache
def resolveUnrealPath(version: Optional[str] = None) -> Optional[Path]:
    r"""Resolve the Unreal Engine installation directory.

    Checks locations in sequence:

    1. ``HKEY_LOCAL_MACHINE\SOFTWARE\EpicGames\Unreal Engine\{version}`` —
       the per-version registry key written by the Unreal installer. 
       Only keys whose name matches the *version* argument (e.g. ``5.7``) are 
       considered.  When *version* is ``None`` the registry is scanned for any 
       version keys and the highest version found is returned.
    2. ``UNREAL_LOCATION`` environment variable — set via ``unreal_env.json``
       for the wrapper bundle.  Takes priority over all other methods.
    3. ``%PROGRAMDATA%\Epic\UnrealEngineLauncher\LauncherInstalled.dat`` —
       the Epic Games Launcher's installation manifest (JSON).  Only entries
       whose ``AppName`` matches ``UE_{version}`` are considered.
    

    When *version* is ``None``, the .dat file and registry are scanned for
    any UE installation and the highest version found is returned.

    Args:
        version: Unreal Engine version string, e.g. ``'5.7'`` or ``'5.4'``.
            May be ``None`` to auto-detect.

    Returns:
        Absolute path to the Unreal Engine installation root directory as a
        :class:`~pathlib.Path`, or ``None`` if no installation could be found.

    """
    # ------------------------------------------------------------------ #
    # 1. Registry  HKLM\SOFTWARE\EpicGames\Unreal Engine\{version}
    # ------------------------------------------------------------------ #
    def _reg_installed_dir(ver: str) -> Optional[str]:
        path = (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\EpicGames\Unreal Engine\{ver}")
        return gt.winreg.getRegistryValue(path, "InstalledDirectory")

    if version:
        location = _reg_installed_dir(version)
        if location:
            log.debug("resolveUnrealPath: found via registry (%s): %r", version, location)
            return Path(location)
        
    # ------------------------------------------------------------------ #
    # 2. UNREAL_LOCATION env var — highest priority
    # ------------------------------------------------------------------ #
    env_location = UNREAL_ENV.get("UNREAL_LOCATION", "").strip()
    if env_location:
        log.debug("resolveUnrealPath: using UNREAL_LOCATION=%r", env_location)
        return Path(env_location)

    # ------------------------------------------------------------------ #
    # 3. LauncherInstalled.dat
    # ------------------------------------------------------------------ #
    if _LAUNCHER_DAT.is_file():
        try:
            with _LAUNCHER_DAT.open(encoding="utf-8") as fh:
                data = json.load(fh)

            # Only consider top-level engine entries (AppName == 'UE_5.7', etc.)
            ue_entries = [
                entry for entry in data.get("InstallationList", [])
                if re.fullmatch(r"UE_\d+\.\d+", entry.get("AppName", ""))
            ]

            if version:
                ue_entries = [e for e in ue_entries if e.get("AppName") == f"UE_{version}"]
            else:
                # Pick the highest version available
                ue_entries.sort(
                    key=lambda e: _sort_version_key(e.get("AppName", "").removeprefix("UE_")),
                    reverse=True,
                )

            if ue_entries:
                location = ue_entries[0].get("InstallLocation", "").strip()
                if location:
                    log.debug("resolveUnrealPath: found via .dat: %r", location)
                    return Path(location)

        except Exception as exc:  # noqa: BLE001
            log.warning("resolveUnrealPath: failed to parse %s: %s", _LAUNCHER_DAT, exc)

    
    else:
        # Enumerate all version subkeys and return the highest that has a value
        subkeys = gt.winreg.getRegistrySubkeys(_EPIC_REGISTRY_BASE) or []
        # Keep only keys that look like a version number (e.g. '5.7', '5.4')
        version_keys = [k for k in subkeys if re.fullmatch(r"\d+\.\d+", k)]
        version_keys.sort(key=_sort_version_key, reverse=True)
        for ver in version_keys:
            location = _reg_installed_dir(ver)
            if location:
                log.debug("resolveUnrealPath: found via registry scan (%s): %r", ver, location)
                return Path(location)

    log.warning("resolveUnrealPath: could not locate Unreal Engine installation (version=%r)", version)
    return None


def resolveUnrealExe(version: Optional[str] = None) -> Optional[Path]:
    r"""Resolve the path to the Unreal Editor executable.

    Builds the canonical path::

        {install_root}/Engine/Binaries/Win64/UnrealEditor.exe

    e.g. ``D:/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe``.

    Args:
        version: Forwarded to :func:`resolveUnrealPath` to pin a specific
            engine version.  Pass ``None`` (the default) to auto-detect.

    Returns:
        :class:`~pathlib.Path` to ``UnrealEditor.exe``, or ``None`` if the
        installation root could not be resolved.

    """
    base = resolveUnrealPath(version=version)
    if base is None:
        return None
    
    # Executable name changed from UE4Editor.exe to UnrealEditor.exe starting in UE 5.
    # To maintain compatibility with older versions we need to check the version before
    # constructing the path.  We can remove this logic once UE4 support is no longer needed.
    base_version = _version_from_path(base)

    if not base_version:
        log.warning("resolveUnrealExe: could not determine version from path %r", base)
        return None

    exe_name = "UnrealEditor.exe" if base_version >= "5" else "UE4Editor.exe"

    return base / "Engine" / "Binaries" / "Win64" / exe_name


def getDxInstaller() -> Optional[os.PathLike]:
    """Get the path to the dxsetup.exe provided by the Unreal package.
    
    Searches for the DirectX installer (dxsetup.exe) in the Unreal Engine
    installation directory.
    
    Returns:
        os.PathLike or None: Path to the DirectX installer if found, None otherwise
        
    Example:
        ```python
        dx_path = getDxInstaller()
        if dx_path:
            print(f"DirectX installer found at: {dx_path}")
        ```
        
    """
    dx_installer = Path(UNREAL_ENV.get("UNREAL_LOCATION", ""))

    if not dx_installer.exists() or not dx_installer.is_dir():
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
    installed_ver = gt.winreg.getRegistryValue(DX_REG_PATH, "Version")
    
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


def isBuildRegistered(version: Optional[str] = None,
                      location: Optional[Path] = None) -> bool:
    """Test if a build is registered in the Epic Games launcher registry.

    Checks the registry key at :data:`UNREAL_BUILDS_PATH` for an entry whose
    version matches *version* and whose path matches *location*.

    When *version* or *location* are ``None`` they are derived from
    :func:`resolveUnrealPath` automatically.

    Args:
        version: Version string such as ``'5.7'``.  Defaults to the version
            parsed from the resolved installation path.
        location: Installation root path.  Defaults to :func:`resolveUnrealPath`.

    Returns:
        bool: True if the build is registered with the correct location, False otherwise

    Example:
        ```python
        if isBuildRegistered():
            print("Current Unreal Engine build is registered")

        if isBuildRegistered("5.3", Path("C:/UnrealEngine/5.3")):
            print("Unreal Engine 5.3 is registered at the correct location")
        ```

    """
    # Resolve defaults from the installation path
    if location is None:
        location = resolveUnrealPath()
    if location is None:
        log.warning("isBuildRegistered: could not resolve installation path")
        return False
    if version is None:
        version = _version_from_path(location)
    if not version:
        log.warning("isBuildRegistered: could not determine version from path %r", location)
        return False
    
    # Check if the build ID exists
    registered_builds = getRegisteredBuilds()
    if not registered_builds:
        return False

    if version not in registered_builds:
        return False

    # Check if the location matches (normalise to forward slashes)
    registered_location = registered_builds[version]
    normalized_location = str(location).replace('\\', '/')
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
    return gt.winreg.getRegistryValues(UNREAL_BUILDS_PATH)


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
    return gt.winreg.getRegistryValue(UNREAL_BUILDS_PATH, build_id)


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
    builds = gt.winreg.getRegistryValues(UNREAL_BUILDS_PATH)
    return list(builds.keys()) if builds else None


def registerBuild(version: Optional[str] = None) -> bool:
    """Register the current Unreal Engine build in the registry.

    Resolves the installation path via :func:`resolveUnrealPath` and derives
    the version (e.g. ``'5.7'``) from the directory name.

    Returns:
        True if registration was successful, False otherwise

    """
    unreal_path = resolveUnrealPath(version=version)
    if unreal_path is None:
        log.error("registerBuild: could not resolve Unreal Engine installation path")
        return False

    build_id = _version_from_path(unreal_path)
    if not build_id:
        log.error("registerBuild: could not determine version from path %r", unreal_path)
        return False

    unreal_location = str(unreal_path).replace('\\', '/')

    if not unreal_path.exists():
        log.warning("registerBuild: Unreal Engine location does not exist: %s", unreal_path)

    # Register the build
    success = gt.winreg.setRegistryValueString(UNREAL_BUILDS_PATH,
                                               build_id,
                                               unreal_location)
    
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
    success = gt.winreg.setRegistryValueString(UNREAL_BUILDS_PATH, build_id, location)
    
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
        # Resolve the current installation path
        current_path = resolveUnrealPath()
        if not current_path:
            log.warning("removeRegisteredBuilds: could not resolve installation path")
            return False

        normalized_current = str(current_path).replace('\\', '/')
        
        # Get all current build registrations
        builds = gt.winreg.getRegistryValues(UNREAL_BUILDS_PATH)
        
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
                if gt.winreg.deleteRegistryValue(UNREAL_BUILDS_PATH, build_id):
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
