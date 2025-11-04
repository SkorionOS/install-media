#!/usr/bin/env bash
# This script runs once in chroot before the airootfs is packed into squashfs
# It is executed by mkarchiso after all packages are installed

set -e -u

echo "=================================="
echo "Running customize_airootfs.sh"
echo "=================================="

# Execute package cleanup
echo "Running package cleanup before packing ISO..."
if [ -f /usr/local/bin/cleanup-packages.sh ]; then
    /usr/local/bin/cleanup-packages.sh
    echo "Package cleanup completed"
else
    echo "Warning: cleanup-packages.sh not found, skipping cleanup"
fi

# Check if headers and dkms were removed
echo "Checking if cleanup was successful..."
if pacman -Qi linux-skchos-headers &>/dev/null; then
    echo "⚠️  WARNING: linux-skchos-headers is still installed!"
    pacman -Qi linux-skchos-headers | grep "Installed Size"
else
    echo "✅ linux-skchos-headers was successfully removed"
fi

if pacman -Qi dkms &>/dev/null; then
    echo "⚠️  WARNING: dkms is still installed!"
else
    echo "✅ dkms was successfully removed"
fi

# Export final package list for release
echo "Exporting final package list..."
pacman -Q > /root/build_info.txt
total_packages=$(wc -l < /root/build_info.txt)
echo "Package list exported to /root/build_info.txt"
echo "Total packages in final ISO: $total_packages"

# Export detailed package list with sizes
echo "Exporting detailed package list with sizes..."
pacman -Qi | awk '
    /^Name/ {name=$3} 
    /^Version/ {version=$3} 
    /^Installed Size/ {size=$4" "$5; printf "%-40s %-20s %s\n", name, version, size}
' | sort -k1 > /root/build_info_detailed.txt
echo "Detailed package list exported to /root/build_info_detailed.txt"

# Log disk usage for troubleshooting
echo "=== Disk usage breakdown ==="
echo "--- Kernel modules ---"
du -sh /usr/lib/modules/* 2>/dev/null || echo "No kernel modules found"
du -sh /usr/lib/modules 2>/dev/null

echo "--- Firmware ---"
du -sh /usr/lib/firmware 2>/dev/null || echo "No firmware found"

echo "--- Top 20 largest directories in /usr ---"
du -h /usr 2>/dev/null | sort -rh | head -20

echo "--- Top 20 largest packages by installed size ---"
pacman -Qi | awk '
    /^Name/ {name=$3} 
    /^Installed Size/ {
        size=$4; 
        unit=$5;
        # Convert to MiB for proper sorting
        if (unit == "KiB") size_mb = size / 1024;
        else if (unit == "MiB") size_mb = size;
        else if (unit == "GiB") size_mb = size * 1024;
        else size_mb = size;
        printf "%.2f MiB %s\n", size_mb, name
    }
' | sort -rn | head -20

echo "--- Kernel package info ---"
pacman -Qi linux-skchos 2>/dev/null | grep -E "Name|Version|Installed Size"

echo "--- Boot files size ---"
ls -lh /boot/ 2>/dev/null || echo "No /boot directory"

echo "--- Initramfs analysis ---"
if [ -f /boot/initramfs-linux-skchos.img ]; then
    INITRAMFS_SIZE=$(du -h /boot/initramfs-linux-skchos.img | cut -f1)
    echo "Original initramfs size: $INITRAMFS_SIZE"
    
    # Detailed analysis
    if [ -f /usr/local/bin/optimize-initramfs.sh ]; then
        echo "Running initramfs optimizer/analyzer..."
        bash /usr/local/bin/optimize-initramfs.sh || echo "Optimizer failed"
    fi
    
    # Firmware optimization is DISABLED
    # Reason: Cannot find a way to reduce initramfs size without breaking GPU
    # - Removing all firmware breaks GPU (tested)
    # - Selective removal doesn't work (mkinitcpio auto-fetches from cache)
    # 
    # Accept the 200MB increase from new kernel, use .iso.xz compression for releases
    
    echo "⚠️ Initramfs firmware optimization: DISABLED"
    echo "New kernel (6.17.7) includes 143M firmware in initramfs (vs 32M in old kernel)"
    echo "This is expected and ensures hardware compatibility"
    
    # Show final initramfs size
    if [ -f /boot/initramfs-linux-skchos.img ]; then
        FINAL_SIZE=$(du -h /boot/initramfs-linux-skchos.img | cut -f1)
        echo "Final initramfs size: $FINAL_SIZE"
    fi
fi

echo "============================"

echo "=================================="
echo "customize_airootfs.sh completed"
echo "=================================="

