"""
Disk utility functions for the graphical installer.
Implements disk selection logic from the original install.sh script.
"""

import subprocess
import re
import os
from ..logger import get_logger

logger = get_logger('disk')


def get_boot_disk():
    """
    Get the current boot disk name (without /dev/).
    Uses efibootmgr to find the boot partition and returns the parent disk.
    
    Returns:
        str: Boot disk name (e.g., "sda", "nvme0n1") or None if not found
    """
    try:
        # Get current boot entry
        result = subprocess.run(
            ['efibootmgr'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            return None
        
        # Find BootCurrent line
        current_boot_id = None
        for line in result.stdout.split('\n'):
            if 'BootCurrent:' in line:
                current_boot_id = line.split(':')[1].strip()
                break
        
        if not current_boot_id:
            return None
        
        # Find boot entry details
        boot_disk_info = None
        for line in result.stdout.split('\n'):
            if f'Boot{current_boot_id}' in line:
                boot_disk_info = line
                break
        
        if not boot_disk_info:
            return None
        
        # Extract partition UUID
        hd_match = re.search(r'HD\([^)]+\)', boot_disk_info)
        if not hd_match:
            return None
        
        hd_parts = hd_match.group(0).split(',')
        if len(hd_parts) < 3:
            return None
        
        part_uuid = hd_parts[2].replace(')', '').replace('0x', '').strip()
        if not part_uuid:
            return None
        
        # Find partition by UUID using blkid
        result = subprocess.run(
            ['blkid'],
            capture_output=True,
            text=True,
            check=False
        )
        
        part_device = None
        for line in result.stdout.split('\n'):
            if part_uuid.lower() in line.lower():
                part_device = line.split(':')[0].replace('/dev/', '')
                break
        
        if not part_device:
            return None
        
        # Get parent disk from partition
        part_path = os.path.realpath(f'/sys/class/block/{part_device}')
        parent_path = os.path.dirname(part_path)
        boot_disk = os.path.basename(parent_path)
        
        return boot_disk
        
    except Exception as e:
        logger.exception(f"Error getting boot disk: {e}")
        return None


def is_disk_external(disk_name):
    """
    Check if a disk is external (USB, etc.).
    
    Args:
        disk_name: Disk name without /dev/ (e.g., "sda")
    
    Returns:
        bool: True if external, False otherwise
    """
    try:
        result = subprocess.run(
            ['lsblk', '--list', '-n', '-o', 'name,hotplug'],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == disk_name:
                return parts[1] == '1'
        
        return False
        
    except Exception as e:
        logger.exception(f"Error checking if disk is external: {e}")
        return False


def is_disk_smaller_than(disk_name, min_size_gb):
    """
    Check if a disk is smaller than the minimum required size.
    
    Args:
        disk_name: Disk name without /dev/ (e.g., "sda")
        min_size_gb: Minimum size in GB
    
    Returns:
        bool: True if disk is smaller than min_size_gb, False otherwise
    """
    try:
        result = subprocess.run(
            ['lsblk', '--list', '-n', '-o', 'name,size'],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == disk_name:
                size_str = parts[1]
                
                # Check for terabytes (always larger than min_size_gb)
                if size_str.endswith('T'):
                    return False
                
                # Check for gigabytes
                if size_str.endswith('G'):
                    size_gb = float(size_str[:-1])
                    return size_gb < min_size_gb
                
                # Anything else (M, K, B) is too small
                return True
        
        # If disk not found, consider it too small
        return True
        
    except Exception as e:
        logger.exception(f"Error checking disk size: {e}")
        return True


def get_disk_model_override(disk_name, device_vendor, device_product, device_cpu):
    """
    Get disk model override from /root/overrides file.
    
    Args:
        disk_name: Disk name without /dev/
        device_vendor: System vendor
        device_product: System product name
        device_cpu: CPU vendor
    
    Returns:
        str: Override model name or None
    """
    overrides_file = '/root/overrides'
    if not os.path.exists(overrides_file):
        return None
    
    try:
        search_key = f'{device_vendor}:{device_product}:{device_cpu}:{disk_name}'
        with open(overrides_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith(search_key):
                    parts = line.split('\t', 1)
                    if len(parts) >= 2:
                        return parts[1].strip()
        return None
    except Exception as e:
        logger.exception(f"Error reading overrides file: {e}")
        return None


def get_disk_human_description(disk_name, device_vendor='', device_product='', device_cpu=''):
    """
    Get human-readable disk description.
    Format: [Transport] Vendor Model (Size)
    Example: [内置] Samsung 970 EVO Plus (500G)
    
    Args:
        disk_name: Disk name without /dev/ (e.g., "sda")
        device_vendor: System vendor (for overrides)
        device_product: System product name (for overrides)
        device_cpu: CPU vendor (for overrides)
    
    Returns:
        str: Human-readable description or None if disk is invalid (size=0B)
    """
    try:
        # Get size
        result = subprocess.run(
            ['lsblk', '--list', '-n', '-o', 'name,size'],
            capture_output=True,
            text=True,
            check=True
        )
        
        size = None
        for line in result.stdout.split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == disk_name:
                size = parts[1]
                break
        
        if not size or size == '0B':
            return None
        
        # Get model (check overrides first)
        model = get_disk_model_override(disk_name, device_vendor, device_product, device_cpu)
        
        if not model:
            result = subprocess.run(
                ['lsblk', '--list', '-n', '-o', 'name,model'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.split('\n'):
                parts = line.split(maxsplit=1)
                if len(parts) >= 2 and parts[0] == disk_name:
                    model = parts[1].strip()
                    break
        
        if not model:
            model = 'Unknown model'
        
        # Get vendor
        result = subprocess.run(
            ['lsblk', '--list', '-n', '-o', 'name,vendor'],
            capture_output=True,
            text=True,
            check=True
        )
        
        vendor = ''
        for line in result.stdout.split('\n'):
            parts = line.split(maxsplit=1)
            if len(parts) >= 2 and parts[0] == disk_name:
                vendor = parts[1].strip()
                break
        
        # Get transport type
        result = subprocess.run(
            ['lsblk', '--list', '-n', '-o', 'name,tran'],
            capture_output=True,
            text=True,
            check=True
        )
        
        transport = ''
        for line in result.stdout.split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == disk_name:
                tran = parts[1].lower()
                # Convert transport to Chinese
                if tran == 'usb':
                    transport = 'USB'
                elif tran in ['nvme', 'sata', 'ata']:
                    transport = '内置'
                elif tran == 'mmc':
                    transport = 'SD卡'
                else:
                    transport = tran.upper()
                break
        
        if not transport:
            transport = '未知'
        
        # Build description
        description = f'[{transport}] {vendor} {model} ({size})'.strip()
        return description
        
    except Exception as e:
        logger.exception(f"Error getting disk description: {e}")
        return None


def list_available_disks(device_vendor='', device_product='', device_cpu=''):
    """
    List all available disks for installation.
    Filters out: zram, boot disk, 0B disks.
    
    Args:
        device_vendor: System vendor (for overrides)
        device_product: System product name (for overrides)
        device_cpu: CPU vendor (for overrides)
    
    Returns:
        list: List of dicts with 'name' and 'description' keys
    """
    boot_disk = get_boot_disk()
    
    try:
        result = subprocess.run(
            ['lsblk', '--list', '-n', '-o', 'name,type'],
            capture_output=True,
            text=True,
            check=True
        )
        
        disks = []
        for line in result.stdout.split('\n'):
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                disk_type = parts[1]
                
                # Filter: only disk type, exclude zram, exclude boot disk
                if disk_type != 'disk':
                    continue
                if 'zram' in name:
                    continue
                if boot_disk and name == boot_disk:
                    continue
                
                # Get description (also filters 0B disks)
                description = get_disk_human_description(
                    name, device_vendor, device_product, device_cpu
                )
                
                if description:
                    disks.append({
                        'name': name,
                        'description': description
                    })
        
        return disks
        
    except Exception as e:
        logger.exception(f"Error listing disks: {e}")
        return []


def check_existing_frzr_installation(disk):
    """
    Check if a disk has an existing frzr installation.
    
    Args:
        disk: Disk name without /dev/ (e.g., "sda")
    
    Returns:
        str: 'complete' - full installation (both frzr_efi and frzr_root exist)
             'incomplete' - remnants (only one of them exists)
             'none' - no installation found
    """
    try:
        result = subprocess.run(
            ['lsblk', '-o', 'LABEL', f'/dev/{disk}'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            return 'none'
        
        labels = result.stdout
        has_efi = labels.count('frzr_efi')
        has_root = labels.count('frzr_root')
        
        if has_efi > 0 and has_root > 0:
            return 'complete'  # Can repair
        elif has_efi > 0 or has_root > 0:
            return 'incomplete'  # Remnants, need cleanup
        else:
            return 'none'  # New disk
            
    except Exception as e:
        logger.exception(f"Error checking frzr installation: {e}")
        return 'none'


def check_free_space(disk):
    """
    Check for available free space on disk (>= 55GB).
    
    Args:
        disk: Disk name without /dev/ (e.g., "sda")
    
    Returns:
        List[dict]: List of free spaces with start_sectors, end_sectors, size_gb
                   Empty list if no sufficient space found
    """
    try:
        result = subprocess.run(
            ['parted', f'/dev/{disk}', 'unit', 's', 'print', 'free'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            return []
        
        free_spaces = []
        for line in result.stdout.split('\n'):
            if 'Free Space' in line:
                parts = line.split()
                if len(parts) >= 3:
                    start = parts[0].replace('s', '')
                    end = parts[1].replace('s', '')
                    
                    try:
                        from ..config import config
                        
                        start_sectors = int(start)
                        end_sectors = int(end)
                        size_sectors = end_sectors - start_sectors
                        
                        # Convert to GB (assuming 512 byte sectors)
                        size_gb = (size_sectors * 512) // (1024 ** 3)
                        
                        if size_gb >= config.min_disk_size:
                            free_spaces.append({
                                'start_sectors': start_sectors,
                                'end_sectors': end_sectors,
                                'size_gb': size_gb
                            })
                    except ValueError:
                        continue
        
        return free_spaces
        
    except Exception as e:
        logger.exception(f"Error checking free space: {e}")
        return []


def list_shrinkable_partitions(disk):
    """
    List partitions that can be shrunk or deleted (>= config.min_disk_size, ntfs/ext4/btrfs).
    
    Args:
        disk: Disk name without /dev/ (e.g., "sda")
    
    Returns:
        List[dict]: List of partitions with path, fstype, size_gb
    """
    from ..config import config
    
    try:
        result = subprocess.run(
            ['lsblk', '-rno', 'NAME,FSTYPE,SIZE', f'/dev/{disk}', '--bytes'],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            return []
        
        partitions = []
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3:
                name = parts[0]
                fstype = parts[1]
                size_bytes = int(parts[2])
                
                # Skip if it's the disk itself
                if name == disk:
                    continue
                
                size_gb = size_bytes // (1024 ** 3)
                
                # Only partitions >= config.min_disk_size with supported filesystems
                if size_gb >= config.min_disk_size and fstype in ['ntfs', 'ext4', 'btrfs']:
                    partitions.append({
                        'path': f'/dev/{name}',
                        'fstype': fstype,
                        'size_gb': size_gb
                    })
        
        return partitions
        
    except Exception as e:
        logger.exception(f"Error listing partitions: {e}")
        return []

