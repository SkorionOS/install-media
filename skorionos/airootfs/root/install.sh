#!/bin/bash
# Version: 2.1.3
# shellcheck disable=SC2034,SC2086,SC2155,SC1091,SC2016,SC2317

set -o pipefail

source $HOME/.dialog

source $HOME/.install

LOG_FILE="${LOG_FILE:-/tmp/frzr.log}"

if [ -z "$SCRIPT_LOGGED" ]; then
    export SCRIPT_LOGGED=1
    echo "" > "$LOG_FILE"
    bash "$0" "$@" 2>&1 | tee "$LOG_FILE"
    exit ${PIPESTATUS[0]}
fi

VERSION="2.1.3"

echo "-------------time: $(date +%Y-%m-%d\ %H:%M:%S) v$VERSION-----------"

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
  # 暂时禁用鼠标支持
  return 0
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
  cancel_install
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

# 通用的异步上传dialog函数
show_upload_dialog() {
    local title="$1"
    local base_message="$2"
    local yes_label="$3"
    local no_label="$4"
    local extra_label="$5"
    
    # 清理旧的临时文件
    rm -f /tmp/upload_result /tmp/upload_status /tmp/dialog_pid
    
    # 后台上传
    {
        sleep 1  # 确保dialog完全启动
        fpaste_url=$(cat $LOG_FILE | fpaste 2>/dev/null)
        if [ -n "${fpaste_url}" ]; then
            echo "$fpaste_url" > /tmp/upload_result
        fi
        echo "done" > /tmp/upload_status
        
        # 从文件读取DIALOG_PID
        if [ -f /tmp/dialog_pid ]; then
            DIALOG_PID=$(cat /tmp/dialog_pid)
            # 检查进程是否还在运行
            if kill -0 $DIALOG_PID 2>/dev/null; then
                # 尝试优雅关闭
                kill -TERM $DIALOG_PID 2>/dev/null
                sleep 0.5
                # 如果还在运行，强制关闭
                if kill -0 $DIALOG_PID 2>/dev/null; then
                    kill -KILL $DIALOG_PID 2>/dev/null
                fi
            fi
        fi
    } &

    # 显示初始dialog
    dialog --colors --title "$title" \
        --yes-label "$yes_label" --no-label "$no_label" \
        --extra-button --extra-label "$extra_label" \
        --yesno "${base_message}\n\n日志上传中..." \
        $MSGBOX_HEIGHT $MSGBOX_WIDTH &
    DIALOG_PID=$!
    
    # 将PID写入文件供后台进程使用
    echo "$DIALOG_PID" > /tmp/dialog_pid
    
    wait $DIALOG_PID
    local ret=$?
    
    # 检查多种可能的退出状态码
    if ([ $ret -eq 143 ] || [ $ret -eq 137 ] || [ $ret -eq 1 ]) && [ -f /tmp/upload_status ]; then
        if [ -f /tmp/upload_result ]; then
            fpaste_msg="\n\n$LOG_FILE 日志已上传至 $(cat /tmp/upload_result)"
        else
            fpaste_msg="\n\n日志上传失败"
        fi
        
        dialog --colors --title "$title" \
            --yes-label "$yes_label" --no-label "$no_label" \
            --extra-button --extra-label "$extra_label" \
            --yesno "${base_message}${fpaste_msg}" \
            $MSGBOX_HEIGHT $MSGBOX_WIDTH
        ret=$?
    fi
    
    # 清理临时文件
    rm -f /tmp/upload_result /tmp/upload_status /tmp/dialog_pid
    
    return $ret
}

cancel_install() {
    cleanup_log
    local msg="$1"
    
    show_upload_dialog \
        "${TITLE_COLOR}$OS_NAME 安装\Zn" \
        "${msg}\n安装已取消, 您还需要要做什么?" \
        "关机" \
        "打开命令行" \
        "重新安装"
    
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

    if [ "$SHOW_UI" == "1" ]; then
      show_upload_dialog \
          "${TITLE_COLOR}$OS_NAME 安装\Zn" \
          "安装结束${msg}, 您还需要要做什么?" \
          "重启" \
          "打开命令行" \
          "重新安装"
      
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
      # 命令行模式：简单的带超时上传
      echo -e "安装结束${msg}\n正在上传日志..."
      if timeout 5 bash -c 'fpaste_url=$(cat '$LOG_FILE' | fpaste 2>/dev/null); echo $fpaste_url' > /tmp/upload_result 2>/dev/null; then
          fpaste_msg="\n$LOG_FILE 日志已上传至 $(cat /tmp/upload_result)"
          rm -f /tmp/upload_result
      else
          fpaste_msg="\n日志上传超时，可稍后手动上传 $LOG_FILE"
      fi
      
      # 命令行显示错误信息，提示用户查看日志。检测用户输入，y重启，n退出，r执行 ~/install.sh 重新安装
      echo -e "${fpaste_msg}\n立即重启? (y/n/r)"
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
                    device_list+=("$name")
                    device_list+=("$description")
            done <<< "$device_output"

            TEMP_FILE=$(mktemp)
            # NOTE: each disk entry consists of 2 elements in the array (disk name & disk description)
            if [ "${#device_list[@]}" -gt 2 ]; then
                    if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装程序 v$VERSION\Zn" --menu "选择一个磁盘来安装 $OS_NAME:" $MENU_HEIGHT $MENU_WIDTH 10 "${device_list[@]}" 2> $TEMP_FILE); then
                            export DISK=$(cat $TEMP_FILE)
                            rm $TEMP_FILE
                    else
                            cancel_install
                    fi
            elif [ "${#device_list[@]}" -eq 2 ]; then
                    # skip selection menu if only a single disk is available to choose from
                    export DISK=${device_list[0]}
            else
                    dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装程序 v$VERSION\Zn" --msgbox "找不到可安装的磁盘\n\n请连接一个容量为64GB或更大的磁盘, 然后重新启动安装程序." $MSGBOX_HEIGHT $MSGBOX_WIDTH
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
                if echo "$filename" | grep -qE "^(chimeraos|skorionos)-.*(\.img(\.tar\.xz|\.xz|\.zst)?|\.skosys)$"; then
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

post_install_with_deployments() {
  local DEPLOY_SUBVOL=$1
  local MOUNT_PATH=${2:-/tmp/frzr_root}
  local DEPLOY_SUBVOL_PATH="${MOUNT_PATH}/${DEPLOY_SUBVOL}"

  echo "正在优化部署: $DEPLOY_SUBVOL"

  steam_sessions="${DEPLOY_SUBVOL_PATH}/usr/share/gamescope-session-plus/sessions.d/steam"
  steam_add_line='    export CLIENTCMD="steam -gamepadui -steamos3 -steampal -steamdeck -noverifyfiles -nobootstrapupdate -skipinitialbootstrap"'
  steam_add_line_2='if [[ ! -f "${HOME}/.steam/root/config/loginusers.vdf" ]] || ! grep -q "AccountName" "${HOME}/.steam/root/config/loginusers.vdf"; then
    export CLIENTCMD="steam -gamepadui -steamos3 -steampal -steamdeck -noverifyfiles -nobootstrapupdate -skipinitialbootstrap"
fi'

  if [ -f "${steam_sessions}" ] && ! grep -q "nobootstrapupdate" "${steam_sessions}"; then
    # 找到含有 'echo "set_bootstrap=1" >>' 的行，在下一行添加 add_line
    sed -i "/echo \"set_bootstrap=1\" >>/a ${steam_add_line}" "${steam_sessions}"
  fi
  if [ -f "${steam_sessions}" ] && ! grep -q "loginusers" "${steam_sessions}"; then
    # 找到含有 'if command -v steam_notif_daemon' 的行，在前面插入多行内容
    # 将多行变量转换为sed可用的格式
    steam_formatted=$(echo "$steam_add_line_2" | sed 's/$/\\/')
    steam_formatted=${steam_formatted%\\}  # 移除最后的反斜杠
    
    sed -i "/if command -v steam_notif_daemon/i\\
$steam_formatted" "${steam_sessions}"
  fi

  steamos_update="${DEPLOY_SUBVOL_PATH}/usr/bin/steamos-update"
  update_add_line='ps -ef | grep -v grep | grep "steamdeck" | grep "steamos" | grep "nobootstrapupdate" >/dev/null && exit 0'
  if [ -f "${steamos_update}" ] && ! grep -q "nobootstrapupdate" "${steamos_update}"; then
    # 找到 'if command -v frzr-deploy' 开头的行， 在前面添加一行 add_line
    sed -i "/if command -v frzr-deploy/i ${update_add_line}" "${steamos_update}"
  fi

}

post_install() {
  echo >&2 "进行后安装步骤"
  # 提示
  # dialog --colors --title "${TITLE_COLOR}提示\Zn" --msgbox "后安装步骤开始" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  local MOUNT_PATH=${1:-/tmp/frzr_root}
  if btrfs subvolume list ${MOUNT_PATH} 2>/dev/null | grep -q -E "deployments/(chimeraos|skorionos)"; then
    current_deploys_array=($(btrfs subvolume list ${MOUNT_PATH} | grep -E "deployments/(chimeraos|skorionos)" | awk '{print $9}'))
    for current_deploy in "${current_deploys_array[@]}"; do
      btrfs property set -fts "${MOUNT_PATH}/${current_deploy}" ro false || true
      post_install_with_deployments "${current_deploy}" "${MOUNT_PATH}"
      btrfs property set -fts "${MOUNT_PATH}/${current_deploy}" ro true || true
    done
  fi

  if [ -f "${MOUNT_PATH}/source" ]; then
    echo >&2 "source 文件处理" 
    sed -i 's#\.[^:]*$##' "${MOUNT_PATH}/source"
    echo >&2 "source 当前内容: $(cat ${MOUNT_PATH}/source)"
  fi
  # 提示
  # dialog --colors --title "${TITLE_COLOR}提示\Zn" --msgbox "后安装步骤结束" $MSGBOX_HEIGHT $MSGBOX_WIDTH
}

# 设置trap
cleanup_triggered=false
trap 'if [ "$cleanup_triggered" = false ]; then cleanup_triggered=true; cleanup_all 1; fi' SIGINT SIGTERM
trap 'if [ "$cleanup_triggered" = false ]; then cleanup_triggered=true; cleanup_all 0; fi' EXIT


if [ $EUID -ne 0 ]; then
  echo "$(basename $0) must be run as root"
  exit 1
fi


OS_NAME=SkorionOS
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
您是否要继续?\n(在后续步骤可进行更详细的安装选项设置)\n\n安装程序版本: v$VERSION" $MSGBOX_HEIGHT $MENU_WIDTH

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
  # dialog --colors --title "${WARNING_COLOR}错误\Zn" --msgbox "frzr-bootstrap 失败\n" $MSGBOX_HEIGHT $MSGBOX_WIDTH
  cancel_install "frzr-bootstrap 失败"
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
  
  # 如果是离线模式，只显示本地安装选项
  if [ "$OFFLINE_MODE" = "true" ]; then
    if (dialog --colors --title "${TITLE_COLOR}安装方式\Zn" --menu "离线模式：仅支持本地镜像安装" $MSGBOX_HEIGHT $MENU_WIDTH 10 \
      "local" "使用本地媒介行安装." \
      2> $TEMP_FILE
    ); then
      CHOICE=$(cat $TEMP_FILE)
      rm $TEMP_FILE
    else
      cancel_install
    fi
  else
    # 在线模式，显示所有选项
    if (dialog --colors --title "${TITLE_COLOR}安装方式\Zn" --menu "你想如何安装SkorionOS ?" $MSGBOX_HEIGHT $MENU_WIDTH 10 \
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
fi

if [[ -z "$SELECTED_FRZR_FILE" && -z "$CHOICE" ]]; then
  # 如果是离线模式且没有本地文件，无法继续
  if [ "$OFFLINE_MODE" = "true" ]; then
    dialog --colors --title "${ERROR_COLOR}无法继续\Zn" \
      --msgbox "离线模式下未找到任何本地安装文件。\n\n请插入包含安装镜像的 USB 设备（标签：FRZR_UPDATE），或重启后连接网络进行在线安装。" \
      $MSGBOX_HEIGHT $MENU_WIDTH
    cancel_install
  else
    # 在线模式，可以使用在线安装
    if (dialog --colors --title "${TITLE_COLOR}安装方式\Zn" --yes-button "在线安装" --no-button "退出安装" --yesno "未找到任何本地安装文件，是否继续使用在线安装方式?" $MSGBOX_HEIGHT $MENU_WIDTH); then
      CHOICE="online"
    else
      cancel_install
    fi
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

  local BOOTSTRAP_PKG="/root/packages/bootstraplinux_ubuntu12_32.tar.xz"

  mkdir -p /root/packages

  tmp_dir=$(mktemp -d)
  echo "tmp_dir: ${tmp_dir}"

  local TMP_FILE="${tmp_dir}/bootstraplinux_ubuntu12_32.tar.xz"
  local DESTINATION="/tmp/frzr_root/etc/first-boot/"
  if [[ ! -d "$DESTINATION" ]]; then
    mkdir -p "$DESTINATION"
  fi

  if [ -n "$SELECTED_FRZR_FILE" ]; then
    local dir_name=$(dirname "$SELECTED_FRZR_FILE")
    if [ -f "$dir_name/bootstraplinux_ubuntu12_32.tar.xz" ]; then
      echo "find $dir_name/bootstraplinux_ubuntu12_32.tar.xz"
      TMP_FILE="$dir_name/bootstraplinux_ubuntu12_32.tar.xz"
      if xz -t "$TMP_FILE"; then
        cp -f "$TMP_FILE" "$DESTINATION"
        echo "copy $TMP_FILE to $DESTINATION success"
        if [ -f "$STEAM_BOOTSTRAP_CONFIG" ]; then
          rm -f "$STEAM_BOOTSTRAP_CONFIG"
        fi
        return 0
      else
        handle_error "Steam 引导文件格式不正确" $?
      fi
    fi
  fi

  if [ -f "$BOOTSTRAP_PKG" ]; then
    if xz -t "$BOOTSTRAP_PKG"; then
      cp -f "$BOOTSTRAP_PKG" "$DESTINATION"
      echo "copy $BOOTSTRAP_PKG to $DESTINATION success"
      return 0
    else
      handle_error "Steam 引导文件格式不正确" $?
    fi
  fi

  local STEAM_URL="https://steamdeck-packages.steamos.cloud/archlinux-mirror/jupiter-main/os/x86_64/steam-jupiter-stable-1.0.0.85-2-x86_64.pkg.tar.zst"
  local STEAM_TMP_PKG="${tmp_dir}/package.pkg.tar.zst"

  if [ ! -f "$STM_PKG" ]; then
    if (curl --http1.1 -# -L -o "${STEAM_TMP_PKG}" -C - "${STEAM_URL}" 2>&1 |
      stdbuf -oL tr '\r' '\n' | grep --line-buffered -oP '[0-9]*+(?=.[0-9])' | clean_progress 100 |
      dialog --gauge "正在下载 Steam ..." 10 50 0 
    ); then
      STM_PKG="$STEAM_TMP_PKG"
    else
      handle_error "下载 Steam 失败" $?
    fi
  fi

  echo "开始从 $STM_PKG 提取 bootstraplinux_ubuntu12_32.tar.xz..."
  
  # 检查文件是否存在于包中，使用更可靠的方法
  echo "验证 Steam 包内容..."
  tar_list_output=$(tar -I zstd -tf "$STM_PKG" 2>/dev/null)
  if [ $? -ne 0 ]; then
    handle_error "无法读取 Steam 包内容" $?
    return 1
  fi
  
  # 使用变量而不是管道来避免时序问题
  if ! echo "$tar_list_output" | grep -q "usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz"; then
    echo "Steam 包中未找到 bootstraplinux_ubuntu12_32.tar.xz 文件"
    echo "包中包含的 steam 相关文件:"
    echo "$tar_list_output" | grep -i steam | head -5
    handle_error "Steam 包结构异常" 1
    return 1
  fi
  
  echo "文件验证通过，开始提取..."
  
  # 提取文件，分离错误输出
  if tar -I zstd -xf "$STM_PKG" usr/lib/steam/bootstraplinux_ubuntu12_32.tar.xz -O >"$TMP_FILE" 2>/dev/null; then
    echo "提取完成，文件大小: $(du -h "$TMP_FILE" | cut -f1)"
    
    # 验证提取的文件
    if [ -s "$TMP_FILE" ] && xz -t "$TMP_FILE" 2>/dev/null; then
      echo "文件验证成功，复制到目标位置..."
      cp -f "$TMP_FILE" "$DESTINATION"
      echo "Steam 引导文件处理完成"
    else
      echo "文件验证失败，检查文件内容..."
      echo "文件前100字节: $(head -c 100 "$TMP_FILE" | hexdump -C)"
      handle_error "提取的 Steam 引导文件格式不正确或为空" 1
    fi
  else
    handle_error "从 Steam 包提取 bootstraplinux_ubuntu12_32.tar.xz 失败" $?
  fi
  
  if [ -f "$STEAM_TMP_PKG" ]; then
    rm "$STEAM_TMP_PKG"
  fi
  
  # 清理临时目录
  if [ -d "$tmp_dir" ]; then
    rm -rf "$tmp_dir"
    echo "清理临时目录: $tmp_dir"
  fi
}

grab_steam_bootstrap

if [ "${CHOICE}" != "local" ]; then
  # Step 1: Select Channel (stable/testing/unstable)
  TEMP_FILE=$(mktemp)
  if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 版本通道选择\Zn" \
    --default-item "stable" \
    --radiolist "请选择系统版本通道 (使用空格键选择)" $MENU_HEIGHT $MENU_WIDTH 3 \
    "stable"   "稳定版 -- 推荐用于日常使用" ON \
    "testing"  "测试版 -- 包含较新功能，可能有未知问题" OFF \
    "unstable" "不稳定版 -- 开发版本，仅用于测试, 可能不稳定" OFF \
    2> $TEMP_FILE
  ); then
    CHANNEL=$(cat $TEMP_FILE)
    rm $TEMP_FILE
  else
    cancel_install
  fi

  # Step 2: Select Desktop Environment (gnome/kde)
  TEMP_FILE=$(mktemp)
  if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 桌面环境选择\Zn" \
    --default-item "gnome" \
    --radiolist "请选择桌面环境 (使用空格键选择)" $MENU_HEIGHT $MENU_WIDTH 2 \
    "gnome" "GNOME 桌面 -- 默认推荐" ON \
    "kde"   "KDE Plasma 桌面 (类似Steam Deck)" OFF \
    2> $TEMP_FILE
  ); then
    DESKTOP=$(cat $TEMP_FILE)
    rm $TEMP_FILE
  else
    cancel_install
  fi

  # Step 3: Select NVIDIA driver option (yes/no)
  TEMP_FILE=$(mktemp)
  if (dialog --colors --title "${TITLE_COLOR}$OS_NAME NVIDIA 驱动选择\Zn" \
    --default-item "no" \
    --radiolist "是否包含 NVIDIA 驱动 (使用空格键选择)\n\n提示：NV 版本在标准版本基础上额外包含 NVIDIA 专有驱动" $MENU_HEIGHT $MENU_WIDTH 2 \
    "no"  "标准版本 -- 仅包含开源驱动" ON \
    "yes" "NV 版本 -- 额外包含 NVIDIA 专有驱动" OFF \
    2> $TEMP_FILE
  ); then
    USE_NVIDIA=$(cat $TEMP_FILE)
    rm $TEMP_FILE
  else
    cancel_install
  fi

  # Construct TARGET from selections
  if [ "$USE_NVIDIA" = "yes" ]; then
    TARGET="${CHANNEL}:${DESKTOP}-nv"
  else
    TARGET="${CHANNEL}:${DESKTOP}"
  fi
fi

TEMP_FILE=$(mktemp)
if (dialog --colors --title "${TITLE_COLOR}$OS_NAME 安装选项\Zn" --menu "安装程序选项" $MENU_HEIGHT $MENU_WIDTH 10 \
  "Standard:" "使用默认选项安装 SkorionOS" \
  "Advanced:" "使用高级选项安装 SkorionOS" \
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
  frzr-deploy "3003n/skorionos:${TARGET}" 2>&1 | tee -a $LOG_FILE
  RESULT=$?
  
  # 关闭提示框
  kill $DIALOG_PID 2>/dev/null
fi

if [ "${RESULT}" == "0" ]; then
  post_install $MOUNT_PATH
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
