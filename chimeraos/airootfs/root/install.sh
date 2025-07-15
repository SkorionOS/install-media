#!/bin/bash
# Version: 1.0.1
# shellcheck disable=SC2034,SC2086,SC2155,SC1091

set -o pipefail

source $HOME/.dialog

source $HOME/.install

LOG_FILE="${LOG_FILE:-/tmp/frzr.log}"

echo "" > $LOG_FILE

if [ -z "$SCRIPT_LOGGED" ]; then
    export SCRIPT_LOGGED=1
    exec script -f "$LOG_FILE" -c "$0 $*"
fi

echo "-------------time: $(date +%Y-%m-%d\ %H:%M:%S)-----------"

# 清理日志中的ANSI转义码
cleanup_log() {
    if [ -f "$LOG_FILE" ]; then
        # 只匹配真正的ANSI转义序列（必须以ESC[开头）
        perl -pi -e 's/\x1b\[[0-9;]*[a-zA-Z]//g; s/\x1b\[[?!][0-9;]*[hlH]//g; s/\x1b\([0-9AB]//g; s/\x1b\[[\d;]*[XG]//g' "$LOG_FILE"
        sed -i '/^Script started on.*\[COMMAND=/d' "$LOG_FILE"
        # 删除空行
        sed -i '/^$/d' "$LOG_FILE"
        # 超过20个空字符的，替换为20个空格
        sed -i 's/[[:space:]]\{21,\}/                    /g' "$LOG_FILE"
    fi
}

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

source $HOME/.dialog

# 显示帮助信息
show_help_old() {
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

show_help() {
  dialog --colors --title "${TITLE_COLOR}帮助\Zn" --msgbox "\
${TEXT_COLOR}键盘导航:\Zn
- TAB: 在选项间切换
- 空格: 选择/取消选择项目
- 方向键: 移动选择
- Enter: 确认选择
- ESC: 取消/返回

${TEXT_COLOR}常见问题:\Zn
- 如果找不到磁盘，检查磁盘连接
- 如果网络连接失败，请检查网络设置
- 安装出错可以查看日志文件" $((MSGBOX_HEIGHT * 2)) $MSGBOX_WIDTH
}

# 错误处理函数
handle_error() {
  local error_msg="$1"
  local error_code="$2"
  
  dialog --colors --title "${TITLE_COLOR}错误\Zn" --msgbox "${WARNING_COLOR}$error_msg\Zn\n错误代码: $error_code" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  
  # 记录错误到日志
  echo "[ERROR] $error_msg (code: $error_code)" >> $LOG_FILE
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
        basename "$(dirname "$part_path")"
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
                sed -e 's/nvme/内置/' | \
                sed -e 's/sata/内置/' | \
                sed -e 's/ata/内置/' | \
                sed -e 's/mmc/SD卡/' | \
                xargs echo -n)
        echo "[${transport}] ${vendor} ${model:=Unknown model} ($size)" | xargs echo -n
}

cancel_install() {
    cleanup_log
    fpaste_url=$(fpaste $LOG_FILE 2>/dev/null)
    if [ -n "${fpaste_url}" ]; then
        fpaste_msg="\n$LOG_FILE 日志已上传至 ${fpaste_url}"
    fi

    dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装\Zn" \
        --yes-label "关机" --no-label "打开命令行" \
        --extra-button --extra-label "重新安装" \
        --yesno "安装已取消, 您还需要要做什么?${fpaste_msg}" $MSGBOX_HEIGHT $MSGBOX_WIDTH
    
    local ret=$?
    case $ret in
        0)  # Yes - 关机
            cleanup_all 0
            poweroff
            ;;
        1)  # No - 打开命令行
            exit 1
            ;;
        3)  # Extra - 重新安装
            cleanup_all 0
            exec ~/install.sh
            ;;
        *)  # ESC或其他
            exit 1
            ;;
    esac
}

finish_install() {
    local msg="$1"
    cleanup_log
    fpaste_url=$(fpaste $LOG_FILE 2>/dev/null)
    if [ -n "${fpaste_url}" ]; then
        fpaste_msg="\n$LOG_FILE 日志已上传至 ${fpaste_url}"
    fi

    if [ "$SHOW_UI" == "1" ]; then
      dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装\Zn" \
        --yes-label "重启" --no-label "打开命令行" \
        --extra-button --extra-label "重新安装" \
        --yesno "安装结束${msg}, 您还需要要做什么?${fpaste_msg}" $MSGBOX_HEIGHT $MSGBOX_WIDTH
    
      local ret=$?
      case $ret in
        0)  # Yes - 重启
            cleanup_all 0
            reboot
            ;;
        1)  # No - 打开命令行
            exit 1
            ;;
        3)  # Extra - 重新安装
            cleanup_all 0
            exec ~/install.sh
            ;;
        *)  # ESC或其他
            exit 1
            ;;
      esac
    else
      # 命令行显示错误信息，提示用户查看日志。检测用户输入，y重启，n退出，r执行 ~/install.sh 重新安装
      echo -e "安装结束${msg}\n${fpaste_msg}\n立即重启? (y/n/r)"
      read -r -n 1 -s -t 60 -p "立即重启? (y/n/r)" input
      echo
      case $input in
      [yY])
        # 在重启前清理
        cleanup_all 0
        reboot
        ;;
      [nN])
        # EXIT trap 会自动处理清理
        exit 1
        ;;
      [rR])
        # 在重新安装前清理
        cleanup_all 0
        exec ~/install.sh
        ;;
      *)
        echo "无效输入"
        ;;
      esac
    fi
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
                    if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装\Zn" --menu "选择一个磁盘来安装 $OS_NAME:" $MENU_HEIGHT $MENU_WIDTH 10 "${device_list[@]}" 2> $TEMP_FILE); then
                            export DISK=$(cat $TEMP_FILE)
                            rm $TEMP_FILE
                    else
                            cancel_install
                    fi
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

# 扫描FRZR_UPDATE文件的函数
scan_frzr_update_files() {
    local menu_list=()
    local file_paths=()
    local temp_mount_base="/tmp/frzr_scan"
    declare -a mounted_by_us=()  # 记录我们挂载的分区，用于后续清理
    local file_index=1
    
    # 显示扫描进度
    dialog --colors --title "${TITLE_COLOR}扫描本地文件\Zn" --infobox "正在扫描分区中的FRZR更新文件..." $MSGBOX_HEIGHT $MSGBOX_WIDTH &
    local dialog_pid=$!
    
    while read -r device_path; do
        # 跳过特殊设备路径
        if [[ "$device_path" =~ /dev/(loop|ram|sr) ]]; then
            continue
        fi
        
        local mount_point=""
        
        # 检查设备是否已挂载
        local existing_mount=$(findmnt -n -o TARGET "$device_path" 2>/dev/null | head -1)
        
        if [ -n "$existing_mount" ]; then
            # 设备已挂载，直接使用
            mount_point="$existing_mount"
        else
            # 设备未挂载，尝试挂载并保持
            local mount_suffix=$(echo "$device_path" | sed 's|/|_|g' | sed 's|^_dev_||')
            mount_point="${temp_mount_base}_${mount_suffix}"
            mkdir -p "$mount_point" 2>/dev/null
            if mount -o rw "$device_path" "$mount_point" 2>/dev/null; then
                mounted_by_us+=("$device_path:$mount_point")  # 记录完整设备路径
            else
                # 挂载失败，跳过此设备
                rmdir "$mount_point" 2>/dev/null
                continue
            fi
        fi

        echo "device_path: $device_path, mount_point: $mount_point" >&2
        
        # 扫描FRZR_UPDATE文件夹
        if [ -d "$mount_point/FRZR_UPDATE" ]; then
            echo "find $mount_point/FRZR_UPDATE" >&2
            while IFS= read -r -d '' file; do
                local filename=$(basename "$file")
                if echo "$filename" | grep -qE "^chimeraos-.*\.img(\.tar\.xz|\.xz|\.zst)?$"; then
                    echo "find $file" >&2
                    local filesize=$(du -h "$file" 2>/dev/null | cut -f1)
                    local device_name=$(basename "$device_path")
                    local display_name="[$device_name] $filename ($filesize)"
                    
                    # 使用序号作为菜单键
                    menu_list+=("$file_index")
                    menu_list+=("$display_name")
                    
                    # 存储文件路径映射
                    file_paths[file_index]="$file"
                    ((file_index++))
                fi
            done < <(find "$mount_point/FRZR_UPDATE" -type f -print0 2>/dev/null)
        else
            echo "not find $mount_point/FRZR_UPDATE" >&2
        fi
        
    done < <(lsblk -ln -o PATH,FSTYPE,TYPE | grep -E "(ntfs|ext4|vfat|exfat|btrfs)" | grep -E "(part|dm|crypt|lvm)" | awk '{print $1}')
    
    # 关闭进度提示
    kill $dialog_pid 2>/dev/null
    
    # 处理扫描结果
    if [ "${#menu_list[@]}" -gt 0 ]; then
        local temp_file=$(mktemp)
        if dialog --colors --title "${TITLE_COLOR}选择FRZR更新文件\Zn" \
            --menu "找到以下可用的更新文件:" $MENU_HEIGHT $MENU_WIDTH 10 \
            "${menu_list[@]}" 2> "$temp_file"; then
            
            local selected_index=$(cat "$temp_file")
            export SELECTED_FRZR_FILE="${file_paths[$selected_index]}"
            # 导出清理信息供后续使用
            export MOUNTED_BY_SCAN="${mounted_by_us[*]}"
            rm "$temp_file"
            return 0
        else
            # 用户取消，清理我们挂载的分区
            cleanup_scan_mounts "${mounted_by_us[@]}"
            rm "$temp_file"
            return 1
        fi
    else
        # 未找到文件，静默清理
        cleanup_scan_mounts "${mounted_by_us[@]}"
        return 0
    fi
}

# 清理函数
cleanup_scan_mounts() {
    local mounts=("$@")
    for mount_info in "${mounts[@]}"; do
        local mount_point=$(echo "$mount_info" | cut -d':' -f2)
        umount "$mount_point" 2>/dev/null
        rmdir "$mount_point" 2>/dev/null
    done
}

# 最终清理函数（安装完成后调用）
cleanup_frzr_mounts() {
    if [ -n "$MOUNTED_BY_SCAN" ]; then
        cleanup_scan_mounts $MOUNTED_BY_SCAN
    fi
}

# 统一的清理函数
cleanup_all() {
    local interrupted=$1
    cleanup_log
    cleanup_frzr_mounts
    exit_gpm
    if [ "$interrupted" = "1" ]; then
        echo "安装被中断"
        exit 1
    fi
}

# 设置trap
trap 'cleanup_all 1' SIGINT SIGTERM
trap 'cleanup_all 0' EXIT


if [ $EUID -ne 0 ]; then
  echo "$(basename $0) must be run as root"
  exit 1
fi


OS_NAME=ChimeraOS
MIN_DISK_SIZE=55 # GB

DEVICE_VENDOR=$(cat /sys/devices/virtual/dmi/id/sys_vendor)
DEVICE_PRODUCT=$(cat /sys/devices/virtual/dmi/id/product_name)
DEVICE_CPU=$(LANG=en_US.UTF-8 lscpu | grep Vendor | cut -d':' -f2 | xargs echo -n)

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
# sleep 2

# TARGET="stable"
check_internet_connection
#######################################

MOUNT_PATH=/tmp/frzr_root

# sets DISK and DISK_DESC
select_disk

# 递归确认安装函数
confirm_installation() {
    dialog --colors --title "${WARNING_COLOR}警告\Zn" --defaultno --yes-button "继续" --no-button "取消安装" --help-button --help-label "帮助" --yesno "\
警告: $OS_NAME 将被安装到以下磁盘: \n\n\
        $DISK - $DISK_DESC\n\n\
您是否要继续?\n(在后续步骤可进行更详细的安装选项设置)" $MSGBOX_HEIGHT $MENU_WIDTH

    local dialog_ret=$?
    
    case $dialog_ret in
        0) # 用户选择"继续"
            return 0
            ;;
        2) # 用户选择"帮助"
            show_help
            # 递归调用自身，继续确认
            confirm_installation
            ;;
        *) # 用户选择"取消安装"或按ESC
            cancel_install
            ;;
    esac
}

# 调用递归确认函数
confirm_installation

# perform bootstrap of disk
if ! frzr-bootstrap gamer "/dev/${DISK}" 2>&1 | tee -a $LOG_FILE; then
  dialog --colors --title "${WARNING_COLOR}错误\Zn" --msgbox "系统引导步骤失败\n请检查 $LOG_FILE 文件以获取更多信息" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  cancel_install
fi

# 遍历所有支持的分区，检索分区根目录存在FRZR_UPDATE文件夹的，列出文件夹中符合规则的文件，并提供选择
if scan_frzr_update_files; then
  if [ -n "$SELECTED_FRZR_FILE" ]; then
    export CHOICE="local"
  fi
else
    cancel_install
fi

if [ -z "$SELECTED_FRZR_FILE" ] && (ls -1 /dev/disk/by-label | grep -q FRZR_UPDATE); then
  TEMP_FILE=$(mktemp)
  if (dialog --colors --title "${TITLE_COLOR}安装方式\Zn" --menu "你想如何安装ChimeraOS ?" $MSGBOX_HEIGHT $MENU_WIDTH 10 \
    "local" "使用本地媒介行安装." \
    "online" "在线获取最新系统镜像." \
    2> $TEMP_FILE
  ); then
    CHOICE=$(cat $TEMP_FILE)
    rm $TEMP_FILE
  else
    cancel_install
  fi
fi

if [[ -z "$SELECTED_FRZR_FILE" && -z "$CHOICE" ]]; then
  if (dialog --colors --title "${TITLE_COLOR}安装方式\Zn" --yes-button "在线安装" --no-button "退出安装" --yesno "未找到任何本地安装文件，是否继续使用在线安装方式?" $MSGBOX_HEIGHT $MENU_WIDTH); then
    CHOICE="online"
  else
    cancel_install
  fi
fi

#### Post install steps for system configuration
# Copy over all network configuration from the live session to the system
SYS_CONN_DIR="/etc/NetworkManager/system-connections"
if [ -d ${SYS_CONN_DIR} ] && [ -n "$(ls -A ${SYS_CONN_DIR})" ]; then
  mkdir -p ${MOUNT_PATH}${SYS_CONN_DIR}
  chmod 700 ${MOUNT_PATH}${SYS_CONN_DIR}
  cp ${SYS_CONN_DIR}/* \
    ${MOUNT_PATH}${SYS_CONN_DIR}/. || handle_error "复制网络配置失败" $?
fi

# Grab the steam bootstrap for first boot
function grab_steam_bootstrap() {
  echo "grab_steam_bootstrap"

  local STEAM_BOOTSTRAP_CONFIG="${MOUNT_PATH}/home/gamer/.config/gamescope/bootstrap.cfg"

  local STM_PKG="/root/packages/steam-jupiter-stable.pkg.tar.zst"

  local TMP_FILE="/tmp/bootstraplinux_ubuntu12_32.tar.xz"
  local DESTINATION="/tmp/frzr_root/etc/first-boot/"
  if [[ ! -d "$DESTINATION" ]]; then
    mkdir -p "$DESTINATION"
  fi

  if [ -n "$SELECTED_FRZR_FILE" ]; then
    local dir_name=$(dirname "$SELECTED_FRZR_FILE")
    if [ -f "$dir_name/bootstraplinux_ubuntu12_32.tar.xz" ]; then
      echo "find $dir_name/bootstraplinux_ubuntu12_32.tar.xz"
      TMP_FILE="$dir_name/bootstraplinux_ubuntu12_32.tar.xz"
      cp "$TMP_FILE" "$DESTINATION"
      echo "copy $TMP_FILE to $DESTINATION success"
      if [ -f "$STEAM_BOOTSTRAP_CONFIG" ]; then
        rm -f "$STEAM_BOOTSTRAP_CONFIG"
      fi
      return 0
    fi
  fi

  local STEAM_URL="https://steamdeck-packages.steamos.cloud/archlinux-mirror/jupiter-main/os/x86_64/steam-jupiter-stable-1.0.0.81-2.5-x86_64.pkg.tar.zst"
  local STEAM_TMP_PKG="/tmp/package.pkg.tar.zst"

  if [ ! -f "$STEAM_TMP_PKG" ]; then
    curl --http1.1 -# -L -o "${STEAM_TMP_PKG}" -C - "${STEAM_URL}" 2>&1 |
      stdbuf -oL tr '\r' '\n' | grep --line-buffered -oP '[0-9]*+(?=.[0-9])' | clean_progress 100 |
      dialog --gauge "正在下载 Steam ..." 10 50 0 || handle_error "下载 Steam 失败" $?
    mv "$STEAM_TMP_PKG" "$STM_PKG"
  fi

  tar -I zstd -xvf "$STM_PKG" usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz -O >"$TMP_FILE" || handle_error "解压 Steam 引导失败" $?
  mv "$TMP_FILE" "$DESTINATION" || handle_error "移动 Steam 引导文件失败" $?
  
  if [ -f "$STEAM_TMP_PKG" ]; then
    rm "$STEAM_TMP_PKG"
  fi
}

grab_steam_bootstrap

if [ "${CHOICE}" != "local" ]; then
  TEMP_FILE=$(mktemp)
  if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 版本选择\Zn" --menu "选择系统版本" $MENU_HEIGHT $MENU_WIDTH 10 \
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
  ); then
    TARGET=$(cat $TEMP_FILE)
    rm $TEMP_FILE
  else
    cancel_install
  fi
fi

TEMP_FILE=$(mktemp)
if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装选项\Zn" --menu "安装程序选项" $MENU_HEIGHT $MENU_WIDTH 10 \
  "Standard:" "使用默认选项安装 ChimeraOS" \
  "Advanced:" "使用高级选项安装 ChimeraOS" \
  2> $TEMP_FILE
  ); then
    MENU_SELECT=$(cat $TEMP_FILE)
    rm $TEMP_FILE
  else
    cancel_install
  fi


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

export NOT_UMOUNT=true

# 创建日志查看按钮
view_log_button() {
  if [ -f "$LOG_FILE" ]; then
    dialog --colors --title "${TITLE_COLOR}安装日志\Zn" --textbox "$LOG_FILE" $MENU_HEIGHT $MENU_WIDTH
  else
    dialog --colors --title "${WARNING_COLOR}错误\Zn" --msgbox "找不到日志文件" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  fi
}

if [ "${CHOICE}" == "local" ]; then
  # 显示安装中提示
  if [ -n "$SELECTED_FRZR_FILE" ]; then
    dialog --colors --title "${TITLE_COLOR}安装进行中\Zn" --infobox "正在安装本地文件: $(basename "$SELECTED_FRZR_FILE")\n\n这可能需要几分钟时间，请耐心等待...\n\n安装日志将保存在 $LOG_FILE" $MSGBOX_HEIGHT $MSGBOX_WIDTH &
    DIALOG_PID=$!
    
    # 在前台运行安装并记录日志，使用选择的文件
    frzr-deploy "$SELECTED_FRZR_FILE" 2>&1 | tee -a $LOG_FILE
    RESULT=$?
  else
    export local_install=true
    dialog --colors --title "${TITLE_COLOR}安装进行中\Zn" --infobox "正在安装本地版本...\n\n这可能需要几分钟时间，请耐心等待...\n\n安装日志将保存在 $LOG_FILE" $MSGBOX_HEIGHT $MSGBOX_WIDTH &
    DIALOG_PID=$!
    
    # 在前台运行安装并记录日志
    frzr-deploy 2>&1 | tee -a $LOG_FILE
    RESULT=$?
  fi
  
  # 关闭提示框
  kill $DIALOG_PID 2>/dev/null
else
  # 显示安装中提示
  dialog --colors --title "${TITLE_COLOR}安装进行中\Zn" --infobox "正在使用在线方式下载安装 ${TARGET} 版本...\n\n这可能需要几分钟时间，请耐心等待...\n\n安装日志将保存在 $LOG_FILE" $MSGBOX_HEIGHT $MSGBOX_WIDTH &
  DIALOG_PID=$!
  
  # 在前台运行安装并记录日志
  frzr-deploy "3003n/chimeraos:${TARGET}" | tee -a $LOG_FILE
  RESULT=$?
  
  # 关闭提示框
  kill $DIALOG_PID 2>/dev/null
fi

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
  # cleanup_log
  # fpaste_url=$(fpaste $LOG_FILE 2>/dev/null)
  # if [ -n "${fpaste_url}" ]; then
  #   fpaste_msg="日志已上传至 ${fpaste_url}"
  # fi
  MSG="安装失败. 请检查 $LOG_FILE 文件以获取更多信息."
fi

echo -e "${MSG} RESULT:${RESULT}\n\n"

finish_install ", RESULT:${RESULT}, ${MSG}"

# cleanup_all 将通过 EXIT trap 自动调用
exit ${RESULT}
