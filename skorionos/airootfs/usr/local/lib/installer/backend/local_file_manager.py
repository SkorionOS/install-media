"""
Local file manager for handling FRZR_UPDATE files with mount lifecycle management.
Mimics the behavior of install.sh's scan_frzr_update_files function.
"""
import os
import re
import subprocess
from typing import List, Dict, Tuple, Optional
from ..logger import get_logger

logger = get_logger('local_file')


class LocalFileManager:
    """
    Manages local FRZR update files with mount lifecycle.
    
    Key behaviors (matching install.sh):
    - Mount partitions when scanning
    - Keep mounted until cleanup is called
    - Only cleanup mounts we created (not pre-existing mounts)
    - Auto-cleanup on object destruction
    """
    
    def __init__(self):
        """Initialize the local file manager."""
        self.mounted_by_us: List[Tuple[str, str]] = []  # [(device, mount_point), ...]
        self.scanned_files: List[Dict[str, str]] = []   # [{'path': ..., 'device': ..., ...}, ...]
        
        # File matching pattern (same as install.sh)
        self.file_pattern = re.compile(
            r'^(chimeraos|skorionos)-.*(\.img(\.tar\.xz|\.xz|\.zst)?|\.skosys)$'
        )
        
        # Supported filesystems (same as install.sh)
        self.supported_fstypes = ['ntfs', 'ext4', 'vfat', 'exfat', 'btrfs']
        
        # Supported device types (same as install.sh)
        self.supported_devtypes = ['part', 'dm', 'crypt', 'lvm']
        
        print("[LocalFileManager] Initialized")
    
    def scan_files(self) -> List[Dict[str, str]]:
        """
        Scan all supported partitions for FRZR_UPDATE files.
        Mounts partitions as needed and keeps them mounted.
        
        Returns:
            List of file dictionaries with keys:
            - path: Full file path (may be on temporary mount)
            - filename: Base filename
            - size: Human-readable size (e.g. "2.5G")
            - device: Device name (e.g. "sda1")
            - display: User-friendly display string
        """
        print("[LocalFileManager] Starting scan...")
        self.scanned_files.clear()
        
        try:
            # Get all block devices with filesystem info
            result = subprocess.run(
                ['lsblk', '-ln', '-o', 'PATH,FSTYPE,TYPE'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) < 3:
                    continue
                
                device_path = parts[0]
                fstype = parts[1]
                devtype = parts[2]
                
                # Skip unsupported devices (same filters as install.sh)
                if devtype not in self.supported_devtypes:
                    continue
                if fstype not in self.supported_fstypes:
                    continue
                if any(skip in device_path for skip in ['/dev/loop', '/dev/ram', '/dev/sr']):
                    continue
                
                # Get or create mount point
                mount_point = self._get_or_mount(device_path)
                if not mount_point:
                    continue
                
                # Scan for FRZR_UPDATE folder
                self._scan_partition(device_path, mount_point)
            
            print(f"[LocalFileManager] Scan complete: {len(self.scanned_files)} files found")
            
        except Exception as e:
            logger.exception(f"[LocalFileManager] Error during scan: {e}")
        
        return self.scanned_files
    
    def _get_or_mount(self, device: str) -> Optional[str]:
        """
        Get existing mount point or create a new temporary mount.
        Only tracks mounts we create (for cleanup).
        
        Args:
            device: Device path (e.g. /dev/sda1)
        
        Returns:
            Mount point path or None if mount failed
        """
        # Check if device is already mounted
        result = subprocess.run(
            ['findmnt', '-n', '-o', 'TARGET,OPTIONS', device],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Device is already mounted - use it, don't track
            lines = result.stdout.strip().split('\n')
            parts = lines[0].split()
            if len(parts) >= 2:
                existing_mount = parts[0]
                mount_options = parts[1]
                
                # Check if mounted read-only
                if 'ro' in mount_options.split(','):
                    print(f"[LocalFileManager] WARNING: {device} is mounted read-only at {existing_mount}")
                    logger.warning(f"Device {device} is read-only, files may be corrupted or filesystem has errors")
                
                print(f"[LocalFileManager] Using existing mount: {device} -> {existing_mount}")
                return existing_mount
        
        # Device not mounted - create temporary mount
        mount_suffix = device.replace('/', '_').replace('_dev_', '')
        mount_point = f"/tmp/frzr_scan_{mount_suffix}"
        
        try:
            os.makedirs(mount_point, exist_ok=True)
            
            # Mount read-write for file operations (needed for local installation merge)
            result = subprocess.run(
                ['mount', '-o', 'rw', device, mount_point],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Verify mount is actually read-write
                verify_result = subprocess.run(
                    ['findmnt', '-n', '-o', 'OPTIONS', mount_point],
                    capture_output=True,
                    text=True
                )
                
                if verify_result.returncode == 0:
                    mount_options = verify_result.stdout.strip()
                    if 'ro' in mount_options.split(','):
                        print(f"[LocalFileManager] WARNING: {device} auto-mounted as read-only (filesystem may have errors)")
                        logger.warning(f"Device {device} is read-only, files may be corrupted")
                
                # Track this mount for cleanup
                self.mounted_by_us.append((device, mount_point))
                print(f"[LocalFileManager] Mounted (rw): {device} -> {mount_point}")
                return mount_point
            else:
                print(f"[LocalFileManager] Mount failed: {device} ({result.stderr.strip()})")
                os.rmdir(mount_point)
                return None
                
        except Exception as e:
            logger.exception(f"[LocalFileManager] Error mounting {device}: {e}")
            return None
    
    def _scan_partition(self, device: str, mount_point: str):
        """
        Scan a mounted partition for FRZR_UPDATE files.
        
        Args:
            device: Device path
            mount_point: Mount point path
        """
        update_dir = os.path.join(mount_point, 'FRZR_UPDATE')
        
        if not os.path.exists(update_dir):
            return
        
        print(f"[LocalFileManager] Scanning {update_dir}...")
        
        try:
            for filename in os.listdir(update_dir):
                # Check if filename matches pattern
                if not self.file_pattern.match(filename):
                    continue
                
                file_path = os.path.join(update_dir, filename)
                
                # Get file size and validate readability
                try:
                    # Check if file is accessible
                    if not os.access(file_path, os.R_OK):
                        print(f"[LocalFileManager] WARNING: File not readable: {filename}")
                        logger.warning(f"File {filename} is not readable, skipping")
                        continue
                    
                    size_bytes = os.path.getsize(file_path)
                    
                    # Sanity check: file should be at least 100MB
                    if size_bytes < 100 * 1024 * 1024:
                        print(f"[LocalFileManager] WARNING: File too small ({size_bytes} bytes): {filename}")
                        logger.warning(f"File {filename} is suspiciously small ({size_bytes} bytes), may be corrupted")
                    
                    size_gb = size_bytes / (1024**3)
                    
                    if size_gb >= 1:
                        size_str = f"{size_gb:.1f}G"
                    else:
                        size_mb = size_bytes / (1024**2)
                        size_str = f"{size_mb:.0f}M"
                    
                    device_name = os.path.basename(device)
                    
                    file_info = {
                        'path': file_path,
                        'filename': filename,
                        'size': size_str,
                        'device': device_name,
                        'display': f"[{device_name}] {filename} ({size_str})"
                    }
                    
                    self.scanned_files.append(file_info)
                    print(f"[LocalFileManager] Found: {file_info['display']}")
                    
                except OSError as e:
                    # I/O error - likely filesystem corruption
                    print(f"[LocalFileManager] ERROR: Cannot read file {filename}: {e}")
                    logger.error(f"I/O error reading {filename} on {device}: {e} - filesystem may be corrupted")
                except Exception as e:
                    logger.exception(f"[LocalFileManager] Error reading file {filename}: {e}")
        
        except Exception as e:
            logger.exception(f"[LocalFileManager] Error scanning {update_dir}: {e}")
    
    def cleanup(self):
        """
        Cleanup all mounts created by this manager.
        Safe to call multiple times.
        """
        if not self.mounted_by_us:
            return
        
        print(f"[LocalFileManager] Cleaning up {len(self.mounted_by_us)} mounts...")
        
        for device, mount_point in self.mounted_by_us:
            try:
                # Unmount
                result = subprocess.run(
                    ['umount', mount_point],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print(f"[LocalFileManager] Unmounted: {mount_point}")
                else:
                    print(f"[LocalFileManager] Unmount failed: {mount_point} ({result.stderr.strip()})")
                
                # Remove mount point directory
                try:
                    os.rmdir(mount_point)
                except Exception as e:
                    logger.warning(f"Cleanup error: {e}")
                
            except Exception as e:
                logger.exception(f"[LocalFileManager] Error cleaning up {mount_point}: {e}")
        
        self.mounted_by_us.clear()
        print("[LocalFileManager] Cleanup complete")
    
    def __del__(self):
        """Auto-cleanup on object destruction (safety net)."""
        self.cleanup()

