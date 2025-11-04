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

# Export final package list for release
echo "Exporting final package list..."
pacman -Q > /root/build_info.txt
total_packages=$(wc -l < /root/build_info.txt)
echo "Package list exported to /root/build_info.txt"
echo "Total packages in final ISO: $total_packages"

echo "=================================="
echo "customize_airootfs.sh completed"
echo "=================================="

