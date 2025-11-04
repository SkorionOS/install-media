#!/bin/bash
# Optimize initramfs to reduce ISO size

set -e

log() {
    echo "[initramfs-optimize] $1"
}

INITRAMFS="/boot/initramfs-linux-skchos.img"

if [ ! -f "$INITRAMFS" ]; then
    log "Initramfs not found at $INITRAMFS"
    exit 0
fi

# Show original size
ORIGINAL_SIZE=$(du -h "$INITRAMFS" | cut -f1)
log "Original initramfs size: $ORIGINAL_SIZE"

# Extract initramfs to analyze
TMPDIR=$(mktemp -d)
cd "$TMPDIR"
log "Extracting initramfs to $TMPDIR..."
lsinitcpio -x "$INITRAMFS" 2>/dev/null || {
    log "Failed to extract initramfs"
    rm -rf "$TMPDIR"
    exit 0
}

# Show largest directories
log "=== Top directories in initramfs ==="
du -h --max-depth=2 2>/dev/null | sort -rh | head -20

# Identify potential size issues
if [ -d "usr/lib/firmware" ]; then
    FIRMWARE_SIZE=$(du -sh usr/lib/firmware 2>/dev/null | cut -f1)
    log "WARNING: Firmware in initramfs: $FIRMWARE_SIZE"
    log "Consider removing unnecessary firmware from initramfs"
fi

if [ -d "usr/lib/modules" ]; then
    MODULE_SIZE=$(du -sh usr/lib/modules 2>/dev/null | cut -f1)
    log "Kernel modules in initramfs: $MODULE_SIZE"
    
    # Count modules
    MODULE_COUNT=$(find usr/lib/modules -name "*.ko*" 2>/dev/null | wc -l)
    log "Number of kernel modules: $MODULE_COUNT"
fi

# Cleanup
cd /
rm -rf "$TMPDIR"

log "Analysis complete. Check logs above for optimization opportunities."

