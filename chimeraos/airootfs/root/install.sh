#!/bin/bash

set -o pipefail

# 对话框类型分组尺寸
MENU_WIDTH=75
MENU_HEIGHT=25

MSGBOX_WIDTH=60
MSGBOX_HEIGHT=10

GAUGE_WIDTH=70
GAUGE_HEIGHT=8

# 统一颜色样式
TITLE_COLOR="\Z1"
TEXT_COLOR="\Z0"
HIGHLIGHT_COLOR="\Z2"
WARNING_COLOR="\Z3"

# 捕获中断信号
trap 'exit_gpm; echo "安装被中断"; exit 1' SIGINT SIGTERM

clean_progress() {
  local scale=$1
  local postfix=$2
  local last_value=$scale
  while IFS= read -r line; do
    value=$((${line} * ${scale} / 100))
    if [ "$last_value" != "$value" ]; then
      echo ${value}${postfix}
      last_value=$value
    fi
  done
}

# 启动鼠标支持
enable_mouse() {
  # 检查gpm是否已安装
  if ! command -v gpm &> /dev/null; then
    return
  fi
  
  # 启动鼠标服务
  gpm -m /dev/input/mice -t imps2 &> /dev/null
  export GPM_PID=$!
}

# 退出gpm
exit_gpm() {
  if [ -n "$GPM_PID" ]; then
    kill $GPM_PID 2>/dev/null
  fi
}

# 设置dialog样式
setup_dialog() {
  # 创建临时配置文件
  export DIALOGRC="/tmp/dialogrc"
  cat > $DIALOGRC << EOF
# Dialog appearance
use_colors = ON
use_shadow = ON
screen_color = (CYAN,BLUE,ON)
shadow_color = (BLACK,BLACK,ON)
dialog_color = (BLACK,WHITE,OFF)
title_color = (BLUE,WHITE,ON)
border_color = (WHITE,WHITE,ON)
button_active_color = (WHITE,BLUE,ON)
button_inactive_color = (BLACK,WHITE,OFF)
button_key_active_color = (WHITE,BLUE,ON)
button_key_inactive_color = (RED,WHITE,OFF)
button_label_active_color = (WHITE,BLUE,ON)
button_label_inactive_color = (BLACK,WHITE,ON)
inputbox_color = (BLACK,WHITE,OFF)
inputbox_border_color = (BLACK,WHITE,OFF)
searchbox_color = (BLACK,WHITE,OFF)
searchbox_title_color = (BLUE,WHITE,ON)
searchbox_border_color = (WHITE,WHITE,ON)
position_indicator_color = (BLUE,WHITE,ON)
menubox_color = (BLACK,WHITE,OFF)
menubox_border_color = (WHITE,WHITE,ON)
item_color = (BLACK,WHITE,OFF)
item_selected_color = (WHITE,BLUE,ON)
tag_color = (BLUE,WHITE,ON)
tag_selected_color = (YELLOW,BLUE,ON)
tag_key_color = (RED,WHITE,OFF)
tag_key_selected_color = (RED,BLUE,ON)
check_color = (BLACK,WHITE,OFF)
check_selected_color = (WHITE,BLUE,ON)
uarrow_color = (GREEN,WHITE,ON)
darrow_color = (GREEN,WHITE,ON)
EOF
}

# 显示帮助信息
show_help() {
  dialog --colors --title "${TITLE_COLOR}帮助\Zn" --msgbox "\
${TEXT_COLOR}键盘导航:\Zn
- TAB: 在选项间切换
- 空格: 选择/取消选择项目
- 方向键: 移动选择
- Enter: 确认选择
- ESC: 取消/返回

${TEXT_COLOR}鼠标操作:\Zn
- 点击按钮: 执行按钮操作
- 点击菜单项: 选择项目
- 点击复选框: 切换选择状态

${TEXT_COLOR}常见问题:\Zn
- 如果找不到磁盘，检查磁盘连接
- 如果网络连接失败，请检查网络设置
- 安装出错可以查看日志文件" $MSGBOX_HEIGHT $MSGBOX_WIDTH
}

# 错误处理函数
handle_error() {
  local error_msg="$1"
  local error_code="$2"
  
  dialog --colors --title "${TITLE_COLOR}错误\Zn" --msgbox "${WARNING_COLOR}$error_msg\Zn\n错误代码: $error_code" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  
  # 记录错误到日志
  echo "[ERROR] $error_msg (code: $error_code)" >> /tmp/install_error.log
}

enable_all_gamepads() {
        # by default, only handheld gamepads are enabled, this enables all other supported gamepads
        busctl set-property org.shadowblip.InputPlumber /org/shadowblip/InputPlumber/Manager \
            org.shadowblip.InputManager \
            ManageAllDevices b 1 &> /dev/null
}

load_gamepad_profile() {
        # load a gamepad profile that emulates a keyboard for interaction with the keyboard based UI
        busctl call org.shadowblip.InputPlumber \
                /org/shadowblip/InputPlumber/CompositeDevice0 \
                org.shadowblip.Input.CompositeDevice \
                LoadProfilePath "s" /root/gamepad_profile.yaml &> /dev/null
}

poll_gamepad() {
        modprobe xpad > /dev/null
        systemctl start inputplumber > /dev/null

        while true; do
                sleep 1
                enable_all_gamepads
                load_gamepad_profile
                if [ $? == 0 ]; then
                        break
                fi
        done
}

get_boot_disk() {
        local current_boot_id=$(efibootmgr | grep BootCurrent | head -1 | cut -d':' -f 2 | tr -d ' ')
        local boot_disk_info=$(efibootmgr | grep "Boot${current_boot_id}" | head -1)
        local part_uuid=$(echo $boot_disk_info | tr "/" "\n" | grep "HD(" | cut -d',' -f3 | head -1 | sed -e 's/^0x//')

        if [ -z $part_uuid ]; then
                # prevent printing errors when the boot disk info is not in a known format
                return
        fi

        local part=$(blkid | grep $part_uuid | cut -d':' -f1 | head -1 | sed -e 's,/dev/,,')
        local part_path=$(readlink "/sys/class/block/$part")
        basename `dirname $part_path`
}

is_disk_external() {
        local disk=$1     # the disk to check if it is external
        local external=$(lsblk --list -n -o name,hotplug | grep "$disk " | cut -d' ' -f2- | xargs echo -n)

        test "$external" == "1"
}

is_disk_smaller_than() {
        local disk=$1     # the disk to check the size of
        local min_size=$2 # minimum size in GB
        local size=$(lsblk --list -n -o name,size | grep "$disk " | cut -d' ' -f2- | xargs echo -n)

        if echo $size | grep "T$" &> /dev/null; then
                return 1
        fi

        if echo $size | grep "G$" &> /dev/null; then
                size=$(echo $size | sed 's/G//' | cut -d'.' -f1)
                if [ "$size" -lt "$min_size" ]; then
                        return 0
                else
                        return 1
                fi
        fi

        return 0
}

get_disk_model_override() {
        local device=$1
        grep "${DEVICE_VENDOR}:${DEVICE_PRODUCT}:${DEVICE_CPU}:${device}" overrides | cut -f2- | xargs echo -n
}

get_disk_human_description() {
        local name=$1
        local size=$(lsblk --list -n -o name,size | grep "$name " | cut -d' ' -f2- | xargs echo -n)

        if [ "$size" = "0B" ]; then
                return
        fi

        local model=$(get_disk_model_override $name | xargs echo -n)
        if [ -z "$model" ]; then
                model=$(lsblk --list -n -o name,model | grep "$name " | cut -d' ' -f2- | xargs echo -n)
        fi

        local vendor=$(lsblk --list -n -o name,vendor | grep "$name " | cut -d' ' -f2- | xargs echo -n)
        local transport=$(lsblk --list -n -o name,tran | grep "$name " | cut -d' ' -f2- | \
                sed -e 's/usb/USB/' | \
                sed -e 's/nvme/Internal/' | \
                sed -e 's/sata/Internal/' | \
                sed -e 's/ata/Internal/' | \
                sed -e 's/mmc/SD card/' | \
                xargs echo -n)
        echo "[${transport}] ${vendor} ${model:=Unknown model} ($size)" | xargs echo -n
}

cancel_install() {
    if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装\Zn" --yes-label "关机" --no-label "打开命令行" --yesno "安装已取消, 您还需要要做什么?" $MSGBOX_HEIGHT $MSGBOX_WIDTH); then
        exit_gpm
        poweroff
    fi

    exit_gpm
    exit 1
}

select_disk() {
    while true
    do
            # a key/value store using an array
            # even number indexes are keys (starting at 0), odd number indexes are values
            # keys are the disk name without `/dev` e.g. sda, nvme0n1
            # values are the disk description
            device_list=()

            boot_disk=$(get_boot_disk)
            if [ -n "$boot_disk" ]; then
                    device_output=$(lsblk --list -n -o name,type | grep disk | grep -v zram | grep -v $boot_disk)
            else
                    device_output=$(lsblk --list -n -o name,type | grep disk | grep -v zram)
            fi

            while read -r line; do
                    name=$(echo "$line" | cut -d' ' -f1 | xargs echo -n)
                    description=$(get_disk_human_description $name)
                    if [ -z "$description" ]; then
                            continue
                    fi
                    device_list+=($name)
                    device_list+=("$description")
            done <<< "$device_output"

            TEMP_FILE=$(mktemp)
            # NOTE: each disk entry consists of 2 elements in the array (disk name & disk description)
            if [ "${#device_list[@]}" -gt 2 ]; then
                    dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装\Zn" --menu "选择一个磁盘来安装 $OS_NAME:" $MENU_HEIGHT $MENU_WIDTH 10 "${device_list[@]}" 2> $TEMP_FILE
                    export DISK=$(cat $TEMP_FILE)
                    rm $TEMP_FILE
            elif [ "${#device_list[@]}" -eq 2 ]; then
                    # skip selection menu if only a single disk is available to choose from
                    export DISK=${device_list[0]}
            else
                    dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装\Zn" --msgbox "找不到可安装的磁盘\n\n请连接一个容量为64GB或更大的磁盘, 然后重新启动安装程序." $MSGBOX_HEIGHT $MSGBOX_WIDTH
                    cancel_install
            fi

            export DISK_DESC=$(get_disk_human_description $DISK)

            if is_disk_smaller_than $DISK $MIN_DISK_SIZE; then
                    if (dialog --colors --title "${WARNING_COLOR}警告\Zn" --yes-button "选择其他磁盘" --no-button "取消安装" \
                            --yesno "错误: 所选磁盘 $DISK - $DISK_DESC 太小. $OS_NAME 需要至少 $MIN_DISK_SIZE GB \n\n请选择其他磁盘." $MSGBOX_HEIGHT $MSGBOX_WIDTH); then
                            continue
                    else
                            cancel_install
                    fi
            fi

            if is_disk_external $DISK; then
                    if (dialog --colors --title "${WARNING_COLOR}警告\Zn" --defaultno --yes-button "继续安装" --no-button "选择其他磁盘" \
                            --yesno "警告: $DISK - $DISK_DESC 似乎是外部磁盘. 在外部磁盘上安装 $OS_NAME 不受官方支持, 可能导致性能不佳和对磁盘造成永久损坏. \n\n您是否仍要继续安装?" $MSGBOX_HEIGHT $MENU_WIDTH); then
                            break
                    else
                            # Unlikely that we would ever have ONLY an external disk, so this should be good enough
                            continue
                    fi
            fi

            break
    done
}




if [ $EUID -ne 0 ]; then
  echo "$(basename $0) must be run as root"
  exit 1
fi


OS_NAME=ChimeraOS
MIN_DISK_SIZE=55 # GB

DEVICE_VENDOR=$(cat /sys/devices/virtual/dmi/id/sys_vendor)
DEVICE_PRODUCT=$(cat /sys/devices/virtual/dmi/id/product_name)
DEVICE_CPU=$(lscpu | grep Vendor | cut -d':' -f2 | xargs echo -n)

# 启动鼠标支持和设置dialog样式
enable_mouse
setup_dialog

dmesg --console-level 1

# start polling for a gamepad
poll_gamepad &

# try to set correct date & time -- required to be able to connect to github via https if your hardware clock is set too far into the past
timedatectl set-ntp true

#### Test connection or ask the user for configuration ####

# Waiting a bit because some wifi chips are slow to scan 5GHZ networks
echo "Starting installer..."
sleep 2

# TARGET="stable"
while ! (curl -Ls --http1.1 https://bing.com | grep '<html' >/dev/null); do
  dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装\Zn" \
    --yes-button "网络配置" \
    --no-button "退出安装" \
    --yesno "未检测到互联网连接。请使用网络配置工具激活网络，然后选择 <退出> 以退出工具并继续安装。" \
    $MSGBOX_HEIGHT $MSGBOX_WIDTH

  if [ $? -ne 0 ]; then
    exit_gpm
    exit 1
  fi

  nmtui-connect
done
#######################################

MOUNT_PATH=/tmp/frzr_root

# sets DISK and DISK_DESC
# select_disk

# warn before erasing disk
# if ! (dialog --colors --title "\Z1警告\Zn" --defaultno --yes-button "擦除磁盘并安装" --no-button "取消安装" "\
# 警告: $OS_NAME 将被安装，以下磁盘上的所有数据将丢失: \n\n\
#         $DISK - $DISK_DESC\n\n\
# 您是否要继续?" 15 70); then
#         cancel_install
# fi

# 修复continue不在循环内的问题
while true; do
  if ! (dialog --colors --title "${WARNING_COLOR}警告\Zn" --defaultno --yes-button "安装" --no-button "取消安装" --help-button --help-label "帮助" --yesno "\
  警告: $OS_NAME 将被安装，如果选择全新安装，以下磁盘上的所有数据将丢失: \n\n\
          $DISK - $DISK_DESC\n\n\
  您是否要继续?" $MSGBOX_HEIGHT $MENU_WIDTH); then
          if [ $? -eq 2 ]; then
              show_help
              continue
          else
              cancel_install
          fi
  fi
  break
done

# perform bootstrap of disk
if ! frzr-bootstrap gamer /dev/${DISK}; then
  dialog --colors --title "${WARNING_COLOR}错误\Zn" --msgbox "系统引导步骤失败\n输入 ~/install.sh 可以重新开始" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  cancel_install
fi

#### Post install steps for system configuration
# Copy over all network configuration from the live session to the system
SYS_CONN_DIR="/etc/NetworkManager/system-connections"
if [ -d ${SYS_CONN_DIR} ] && [ -n "$(ls -A ${SYS_CONN_DIR})" ]; then
  mkdir -p -m=700 ${MOUNT_PATH}${SYS_CONN_DIR}
  cp ${SYS_CONN_DIR}/* \
    ${MOUNT_PATH}${SYS_CONN_DIR}/. || handle_error "复制网络配置失败" $?
fi

# Grab the steam bootstrap for first boot

# URL="https://steamdeck-packages.steamos.cloud/archlinux-mirror/jupiter-main/os/x86_64/steam-jupiter-stable-1.0.0.79-1.1-x86_64.pkg.tar.zst"
# TMP_PKG="/tmp/package.pkg.tar.zst"
STM_PKG="/root/packages/steam-jupiter-stable.pkg.tar.zst"
TMP_FILE="/tmp/bootstraplinux_ubuntu12_32.tar.xz"
DESTINATION="/tmp/frzr_root/etc/first-boot/"
if [[ ! -d "$DESTINATION" ]]; then
  mkdir -p /tmp/frzr_root/etc/first-boot
fi

# curl --http1.1 -# -L -o "${TMP_PKG}" -C - "${URL}" 2>&1 |
#   stdbuf -oL tr '\r' '\n' | grep --line-buffered -oP '[0-9]*+(?=.[0-9])' | clean_progress 100 |
#   dialog --gauge "正在下载 Steam ..." 10 50 0

tar -I zstd -xvf "$STM_PKG" usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz -O >"$TMP_FILE" || handle_error "解压 Steam 引导失败" $?
mv "$TMP_FILE" "$DESTINATION" || handle_error "移动 Steam 引导文件失败" $?
# rm "$TMP_PKG"

TEMP_FILE=$(mktemp)
dialog --colors --title "${TITLE_COLOR}$OS_NAME 版本选择\Zn" --menu "选择系统版本" $MENU_HEIGHT $MENU_WIDTH 10 \
  "stable:gnome"         "stable:gnome      稳定版 (GNOME) -- 默认" \
  "testing:gnome"        "testing:gnome     测试版 (GNOME)" \
  "unstable:gnome"       "unstable:gnome    不稳定版 (GNOME)" \
  "stable:kde"           "stable:kde        稳定版 (KDE)" \
  "testing:kde"          "testing:kde       测试版 (KDE)" \
  "unstable:kde"         "unstable:kde      开发版 (KDE)" \
  "stable:gnome-nv"      "stable:gnome-nv   稳定版 (GNOME NVIDIA)" \
  "testing:gnome-nv"     "testing:gnome-nv  测试版 (GNOME NVIDIA)" \
  "unstable:gnome-nv"    "unstable:gnome-nv 不稳定版 (GNOME NVIDIA)" \
  "stable:kde-nv"        "stable:kde-nv     稳定版 (KDE NVIDIA)" \
  "testing:kde-nv"       "testing:kde-nv    测试版 (KDE NVIDIA)" \
  "unstable:kde-nv"      "unstable:kde-nv   不稳定版 (KDE NVIDIA)" \
  2> $TEMP_FILE
TARGET=$(cat $TEMP_FILE)
rm $TEMP_FILE

TEMP_FILE=$(mktemp)
dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装选项\Zn" --menu "安装程序选项" $MENU_HEIGHT $MENU_WIDTH 10 \
  "Standard:" "使用默认选项安装 ChimeraOS" \
  "Advanced:" "使用高级选项安装 ChimeraOS" \
  2> $TEMP_FILE
MENU_SELECT=$(cat $TEMP_FILE)
rm $TEMP_FILE

_SHOW_UI=1

firmware_overrides_opt="使用固件覆盖"
cdn_opt="CDN 加速"
fallback_opt="使用备用源"
shou_ui_opt="显示安装界面"
debug_opt="Debug 模式"

if [ "$MENU_SELECT" = "Advanced:" ]; then
  TEMP_FILE=$(mktemp)
  dialog --colors --title "${TITLE_COLOR}高级选项\Zn" --separate-output --checklist "使用空格键切换选中, 回车直接完成" $MENU_HEIGHT $MENU_WIDTH 10 \
    "$firmware_overrides_opt" "DSDT/EDID" OFF \
    "$cdn_opt" "" OFF \
    "$fallback_opt" "" ON \
    "$shou_ui_opt" "" ON \
    "$debug_opt" "" OFF \
    2> $TEMP_FILE
  OPTIONS=$(cat $TEMP_FILE)
  rm $TEMP_FILE

  if echo "$OPTIONS" | grep -q "$firmware_overrides_opt"; then
    echo "启用固件覆盖..."
    if [[ ! -d "/tmp/frzr_root/etc/device-quirks/" ]]; then
      mkdir -p "/tmp/frzr_root/etc/device-quirks"
      # Create device-quirks default config
      cat >"/tmp/frzr_root/etc/device-quirks/device-quirks.conf" <<EOL
export USE_FIRMWARE_OVERRIDES=1
export USB_WAKE_ENABLED=1
EOL
      # Create dsdt_override.log with default values
      cat >"/tmp/frzr_root/etc/device-quirks/dsdt_override.log" <<EOL
LAST_DSDT=None
LAST_BIOS_DATE=None
LAST_BIOS_RELEASE=None
LAST_BIOS_VENDOR=None
LAST_BIOS_VERSION=None
EOL
    fi
  fi

  if echo "$OPTIONS" | grep -q "$cdn_opt"; then
    sed -i "s/^release_cdn.*/release_cdn = true/" /etc/frzr-sk.conf
    sed -i "s/^api_cdn.*/api_cdn = true/" /etc/frzr-sk.conf
  else
    sed -i "s/^release_cdn.*/release_cdn = false/" /etc/frzr-sk.conf
    sed -i "s/^api_cdn.*/api_cdn = false/" /etc/frzr-sk.conf
  fi

  if echo "$OPTIONS" | grep -q "$fallback_opt"; then
    sed -i "s/^fallback_url.*/fallback_url = true/" /etc/frzr-sk.conf
  else
    sed -i "s/^fallback_url.*/fallback_url = false/" /etc/frzr-sk.conf
  fi

  if echo "$OPTIONS" | grep -q "$shou_ui_opt"; then
    _SHOW_UI=1
  else
    _SHOW_UI=""
  fi

  if echo "$OPTIONS" | grep -q "$debug_opt"; then
    export DEBUG=1
  fi
fi

export SHOW_UI="${_SHOW_UI}"

if (ls -1 /dev/disk/by-label | grep -q FRZR_UPDATE); then
  TEMP_FILE=$(mktemp)
  dialog --colors --title "${TITLE_COLOR}安装方式\Zn" --menu "你想如何安装ChimeraOS ?" $MSGBOX_HEIGHT $MENU_WIDTH 10 \
    "local" "使用本地媒介行安装." \
    "online" "在线获取最新系统镜像." \
    2> $TEMP_FILE
  CHOICE=$(cat $TEMP_FILE)
  rm $TEMP_FILE
fi

export NOT_UMOUNT=true

# 创建一个进度条FIFO
FIFO=$(mktemp -u)
mkfifo $FIFO

# 创建日志查看按钮
view_log_button() {
  if [ -f "/tmp/frzr.log" ]; then
    dialog --colors --title "${TITLE_COLOR}安装日志\Zn" --textbox "/tmp/frzr.log" $MENU_HEIGHT $MENU_WIDTH
  else
    dialog --colors --title "${WARNING_COLOR}错误\Zn" --msgbox "找不到日志文件" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  fi
}

if [ "${CHOICE}" == "local" ]; then
  export local_install=true
  # 在后台运行frzr-deploy并将输出发送到FIFO
  (frzr-deploy | tee /tmp/frzr.log) &> $FIFO &
  # 显示进度条
  dialog --colors --title "${TITLE_COLOR}安装进度\Zn" --gauge "正在安装本地版本..." $GAUGE_HEIGHT $GAUGE_WIDTH 0 < $FIFO
  # 获取命令的返回值
  wait $!
  RESULT=$?
else
  # 在后台运行frzr-deploy并将输出发送到FIFO
  (frzr-deploy "3003n/chimeraos:${TARGET}" | tee /tmp/frzr.log) &> $FIFO &
  # 显示进度条
  dialog --colors --title "${TITLE_COLOR}安装进度\Zn" --gauge "正在安装 ${TARGET} 版本..." $GAUGE_HEIGHT $GAUGE_WIDTH 0 < $FIFO
  # 获取命令的返回值
  wait $!
  RESULT=$?
fi

# 删除FIFO
rm $FIFO

MSG="安装失败."
if [ "${RESULT}" == "0" ]; then
  BOOT_CFG="${MOUNT_PATH}/boot/loader/entries/frzr.conf"
  if [[ ! -f "${BOOT_CFG}" ]]; then
    if [[ -n "$BOOT_CFG_PARA" ]]; then
      echo "${BOOT_CFG_PARA}" >"${BOOT_CFG}"
      echo "default frzr.conf" >"${MOUNT_PATH}/boot/loader/loader.conf"
    else
      MSG="安装失败. 未找到启动配置文件."
    fi
  else
    MSG="安装成功完成"
  fi
elif [ "${RESULT}" == "29" ]; then
  MSG="遇到 GitHub API 速率限制错误, 请稍后重试安装"
else
  fpaste_url=$(fpaste /tmp/frzr.log 2>/dev/null)
  if [ -n "${fpaste_url}" ]; then
    fpaste_msg="日志已上传至 ${fpaste_url}"
  fi
  MSG="安装失败. 请检查 /tmp/frzr.log 文件以获取更多信息. ${fpaste_msg}"
fi

echo -e "${MSG} RESULT:${RESULT}\n\n"

if [ "$SHOW_UI" == "1" ]; then
  if (dialog --colors --title "${TITLE_COLOR}安装完成\Zn" --yes-button "重启" --no-button "取消" --help-button --help-label "查看日志" --yesno "${MSG} RESULT:${RESULT}\n\n立即重启?" $MSGBOX_HEIGHT $MSGBOX_WIDTH); then
    # 在退出前清理GPM
    exit_gpm
    reboot
  elif [ $? -eq 2 ]; then
    view_log_button
    # 再次询问是否重启
    if (dialog --colors --title "${TITLE_COLOR}安装完成\Zn" --yesno "${MSG} RESULT:${RESULT}\n\n立即重启?" $MSGBOX_HEIGHT $MSGBOX_WIDTH); then
      exit_gpm
      reboot
    fi
  fi
else
  # 命令行显示错误信息，提示用户查看日志。检测用户输入，y重启，n退出，r执行 ~/install.sh 重新安装
  echo -e "${MSG} RESULT:${RESULT}\n\n立即重启? (y/n/r)"
  read -r -n 1 -s -t 60 -p "立即重启? (y/n/r)" input
  echo
  case $input in
  [yY])
    # 在退出前清理GPM
    exit_gpm
    reboot
    ;;
  [nN])
    # 在退出前清理GPM
    exit_gpm
    exit 1
    ;;
  [rR])
    # 在退出前清理GPM
    exit_gpm
    ~/install.sh
    ;;
  *)
    echo "无效输入"
    ;;
  esac
fi

# 在退出前清理GPM
exit_gpm

exit ${RESULT}
