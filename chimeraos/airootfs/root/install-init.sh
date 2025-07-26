#!/bin/bash
# shellcheck disable=SC2034,SC2086,SC2155,SC1091

source "$HOME/.dialog"
source "$HOME/.install"

INSTALL_SCRIPT="$HOME/install.sh"

SCRIPT_URL="https://github.com/3003n/install-media/raw/dialog/chimeraos/airootfs/root/install.sh"
SCRIPT_URL_FALLBACK="https://gitee.com/honjow/install-media/raw/dialog/chimeraos/airootfs/root/install.sh"

function check_and_update_install_script() {
    local current_version=""
    local remote_version=""
    local temp_script="/tmp/install_new.sh"
    local timeout_main=5    # 主URL超时
    local timeout_backup=10 # 备用URL超时
    
    # 获取当前脚本版本
    if [ -f "$INSTALL_SCRIPT" ]; then
        current_version=$(grep "^# Version:" "$INSTALL_SCRIPT" | head -1 | sed 's/^# Version: //')
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
    
    # 获取远程版本
    remote_version=$(grep "^# Version:" "$temp_script" | head -1 | sed 's/^# Version: //')
    
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

eval "$INSTALL_SCRIPT"
