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
pacman -Qi | awk '/^Name/{name=$3} /^Installed Size/{size=$4" "$5; print size, name}' | sort -rh | head -20

echo "--- Kernel package info ---"
pacman -Qi linux-skchos 2>/dev/null | grep -E "Name|Version|Installed Size"

echo "============================"

echo "=================================="
echo "customize_airootfs.sh completed"
echo "=================================="

