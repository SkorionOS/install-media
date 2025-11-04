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
    
    # Optimize initramfs by removing WiFi firmware only (GPU firmware is needed!)
    echo "Optimizing initramfs - removing WiFi firmware only..."
    
    if [ -d /usr/lib/firmware ]; then
        # Only remove WiFi firmware (not needed for boot)
        # GPU firmware MUST be kept for graphics initialization
        mkdir -p /tmp/firmware_removed
        
        echo "Removing WiFi firmware (not needed for boot)..."
        # WiFi firmware - these are large and only needed after system boots
        [ -d /usr/lib/firmware/intel ] && [ -d /usr/lib/firmware/intel/iwlwifi ] && \
            mv /usr/lib/firmware/intel/iwlwifi /tmp/firmware_removed/
        [ -d /usr/lib/firmware/ath10k ] && mv /usr/lib/firmware/ath10k /tmp/firmware_removed/
        [ -d /usr/lib/firmware/ath11k ] && mv /usr/lib/firmware/ath11k /tmp/firmware_removed/
        [ -d /usr/lib/firmware/brcm ] && mv /usr/lib/firmware/brcm /tmp/firmware_removed/
        [ -d /usr/lib/firmware/rtl_nic ] && mv /usr/lib/firmware/rtl_nic /tmp/firmware_removed/
        [ -d /usr/lib/firmware/rtlwifi ] && mv /usr/lib/firmware/rtlwifi /tmp/firmware_removed/
        [ -d /usr/lib/firmware/mediatek ] && mv /usr/lib/firmware/mediatek /tmp/firmware_removed/
        
        REMOVED_SIZE=$(du -sh /tmp/firmware_removed 2>/dev/null | cut -f1 || echo "0")
        echo "Removed WiFi firmware: $REMOVED_SIZE"
        echo "GPU firmware: KEPT (required for graphics)"
        
        # Regenerate initramfs
        echo "Regenerating initramfs..."
        mkinitcpio -P 2>&1 | tail -20
        
        # Restore WiFi firmware for runtime use
        echo "Restoring WiFi firmware for runtime..."
        if [ -d /tmp/firmware_removed/iwlwifi ]; then
            mkdir -p /usr/lib/firmware/intel
            mv /tmp/firmware_removed/iwlwifi /usr/lib/firmware/intel/
        fi
        [ -d /tmp/firmware_removed/ath10k ] && mv /tmp/firmware_removed/ath10k /usr/lib/firmware/
        [ -d /tmp/firmware_removed/ath11k ] && mv /tmp/firmware_removed/ath11k /usr/lib/firmware/
        [ -d /tmp/firmware_removed/brcm ] && mv /tmp/firmware_removed/brcm /usr/lib/firmware/
        [ -d /tmp/firmware_removed/rtl_nic ] && mv /tmp/firmware_removed/rtl_nic /usr/lib/firmware/
        [ -d /tmp/firmware_removed/rtlwifi ] && mv /tmp/firmware_removed/rtlwifi /usr/lib/firmware/
        [ -d /tmp/firmware_removed/mediatek ] && mv /tmp/firmware_removed/mediatek /usr/lib/firmware/
        rm -rf /tmp/firmware_removed
        echo "WiFi firmware available for runtime"
    fi
    
    # Show new size
    if [ -f /boot/initramfs-linux-skchos.img ]; then
        NEW_SIZE=$(du -h /boot/initramfs-linux-skchos.img | cut -f1)
        echo "Optimized initramfs size: $NEW_SIZE"
        echo "Size reduction: $(echo "$INITRAMFS_SIZE -> $NEW_SIZE")"
    fi
fi

if [ -f /boot/initramfs-linux-skchos-fallback.img ]; then
    FALLBACK_SIZE=$(du -h /boot/initramfs-linux-skchos-fallback.img | cut -f1)
    echo "⚠️  WARNING: Fallback initramfs exists! Size: $FALLBACK_SIZE"
    echo "Removing fallback to save space..."
    rm -f /boot/initramfs-linux-skchos-fallback.img
fi

echo "============================"

echo "=================================="
echo "customize_airootfs.sh completed"
echo "=================================="

