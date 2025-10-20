#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="skorionos${VARIANT_SUFFIX:-}"
iso_label="SKORIONOS_$(date +%Y%m)"
iso_publisher="SkorionOS <https://github.com/3003n/SkorionOS>"
iso_application="SkorionOS Installer"
iso_version=$(date +%Y.%m.%d)
install_dir="arch"
buildmodes=('iso')
bootmodes=('bios.syslinux' 'uefi.systemd-boot')
arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86' '-b' '1M' '-Xdict-size' '1M')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/install.sh"]="0:0:755"
  ["/root/install-init.sh"]="0:0:755"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/bin"]="0:0:755"
  ["/root/bin/update-frzr"]="0:0:755"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
  ["/usr/local/bin/cleanup-packages.sh"]="0:0:755"
)
