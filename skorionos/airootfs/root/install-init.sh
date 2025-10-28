#!/bin/bash
# shellcheck disable=SC2034,SC2086,SC2155,SC1091

source "$HOME/.dialog"
source "$HOME/.install"

INSTALL_SCRIPT="$HOME/install.sh"

SCRIPT_URL="https://github.com/3003n/install-media/raw/skorionos/skorionos/airootfs/root/install.sh"
SCRIPT_URL_FALLBACK="https://gitee.com/honjow/install-media/raw/skorionos/skorionos/airootfs/root/install.sh"

function check_and_update_install_script() {
    local current_version=""
    local remote_version=""
    local temp_script="/tmp/install_new.sh"
    local timeout_main=5    # 主URL超时
    local timeout_backup=10 # 备用URL超时
    
    # 获取当前脚本版本（支持两种格式）
    if [ -f "$INSTALL_SCRIPT" ]; then
        # 优先尝试变量形式 VERSION="x.x.x"
        current_version=$(grep "^VERSION=" "$INSTALL_SCRIPT" | head -1 | sed 's/^VERSION="\(.*\)"/\1/')
        # 如果变量形式不存在，尝试注释形式 # Version: x.x.x
        if [ -z "$current_version" ]; then
            current_version=$(grep "^# Version:" "$INSTALL_SCRIPT" | head -1 | sed 's/^# Version: //')
        fi
    fi
    
    # 尝试从主URL下载
    if curl -L --connect-timeout $timeout_main --max-time $timeout_main -f -s -o "$temp_script" "$SCRIPT_URL"; then
        echo "从主URL下载成功"
    # 主URL失败，尝试备用URL
    elif curl -L --connect-timeout $timeout_backup --max-time $timeout_backup -f -s -o "$temp_script" "$SCRIPT_URL_FALLBACK"; then
        echo "从备用URL下载成功"
    else
        echo "所有URL下载失败，使用本地脚本"
        return 1
    fi
    
    # 验证下载的脚本
    if ! validate_script "$temp_script"; then
        echo "下载的脚本验证失败"
        rm -f "$temp_script"
        return 1
    fi
    
    # 获取远程版本（支持两种格式）
    # 优先尝试变量形式 VERSION="x.x.x"
    remote_version=$(grep "^VERSION=" "$temp_script" | head -1 | sed 's/^VERSION="\(.*\)"/\1/')
    # 如果变量形式不存在，尝试注释形式 # Version: x.x.x
    if [ -z "$remote_version" ]; then
        remote_version=$(grep "^# Version:" "$temp_script" | head -1 | sed 's/^# Version: //')
    fi
    
    # 版本比较和更新
    if [ -n "$remote_version" ] && version_greater "$remote_version" "$current_version"; then
        echo "发现新版本: $current_version -> $remote_version"
        cp "$temp_script" "$INSTALL_SCRIPT"
        chmod +x "$INSTALL_SCRIPT"
        echo "脚本更新完成"
    else
        echo "已是最新版本: $current_version"
    fi
    
    rm -f "$temp_script"
    sleep 3
}

# 脚本验证函数
function validate_script() {
    local script_file="$1"
    
    # 检查文件是否存在且不为空
    [ -f "$script_file" ] && [ -s "$script_file" ] || return 1
    
    # 检查是否为bash脚本
    head -1 "$script_file" | grep -q "^#!/bin/bash" || return 1
    
    # 语法检查
    bash -n "$script_file" || return 1
    
    # 检查关键函数是否存在（可选）
    grep -q "function.*select_disk\|select_disk()" "$script_file" || return 1
    
    return 0
}

# 版本比较函数
function version_greater() {
    local ver1="$1"
    local ver2="$2"
    
    # 如果当前版本为空，认为远程版本更新
    [ -z "$ver2" ] && return 0
    
    # 简单的版本比较（基于字符串排序）
    [ "$(printf '%s\n' "$ver1" "$ver2" | sort -V | tail -1)" = "$ver1" ] && [ "$ver1" != "$ver2" ]
}

poll_gamepad &

copy_system_configs

check_internet_connection

check_and_update_install_script

# ===== Select installer mode =====
INSTALLER_MODE=""

# Check if graphical installer is available
if command -v gamescope &> /dev/null && \
   command -v python3 &> /dev/null && \
   python3 -c "import gi; gi.require_version('Gtk', '4.0')" 2>/dev/null && \
   [ -f /usr/local/bin/installer-poc ]; then
  
  TEMP_FILE=$(mktemp)
  if (dialog --colors --title "\Z1SkorionOS 安装器\Zn" \
    --default-item "text" \
    --menu "请选择安装器模式" 15 70 2 \
    "text" "文本安装器 -- 默认，稳定可靠" \
    "poc"  "图形化安装器 -- PoC 测试版，验证新界面" \
    2> $TEMP_FILE
  ); then
    INSTALLER_MODE=$(cat $TEMP_FILE)
    rm $TEMP_FILE
  else
    # User cancelled, default to text mode
    INSTALLER_MODE="text"
    rm $TEMP_FILE
  fi
else
  # Graphical installer not available, use text mode
  INSTALLER_MODE="text"
fi

# Launch installer based on selection
case "$INSTALLER_MODE" in
  poc)
    clear
    echo "启动图形化安装器 PoC..."
    exec /usr/local/bin/installer-poc
    ;;
  text|*)
    # Default text mode
    eval "$INSTALL_SCRIPT"
    ;;
esac
