#!/bin/bash
# shellcheck disable=SC2034,SC2086,SC2155,SC1091

source "$HOME/.dialog"
source "$HOME/.install"

INSTALL_SCRIPT="$HOME/installer-text.sh"

SCRIPT_URL="https://github.com/3003n/install-media/raw/skorionos/skorionos/airootfs/root/installer-text.sh"
SCRIPT_URL_FALLBACK="https://gitee.com/honjow/install-media/raw/skorionos/skorionos/airootfs/root/installer-text.sh"

# ===== Controller Support (InputPlumber) =====
function setup_controller_support() {
    echo "Setting up controller support..."
    
    # Load xpad kernel module for Xbox controllers
    modprobe xpad &> /dev/null
    
    # Start InputPlumber service
    if ! systemctl is-active --quiet inputplumber; then
        echo "Starting InputPlumber service..."
        systemctl start inputplumber &> /dev/null
        
        # Wait for InputPlumber to be ready (max 10 seconds)
        local max_wait=10
        local waited=0
        while [ $waited -lt $max_wait ]; do
            if busctl status org.shadowblip.InputPlumber &> /dev/null; then
                echo "InputPlumber service is ready"
                break
            fi
            sleep 1
            waited=$((waited + 1))
        done
        
        if [ $waited -ge $max_wait ]; then
            echo "Warning: InputPlumber service did not start in time"
            return 1
        fi
    else
        echo "InputPlumber service already running"
    fi
    
    # Enable management of all gamepad devices
    echo "Enabling all gamepad devices..."
    if busctl set-property org.shadowblip.InputPlumber \
        /org/shadowblip/InputPlumber/Manager \
        org.shadowblip.InputManager \
        ManageAllDevices b 1 &> /dev/null; then
        echo "All gamepad devices enabled"
    else
        echo "Warning: Failed to enable all gamepad devices"
    fi
    
    # Wait a bit for devices to be detected
    sleep 2
    
    # Load gamepad profile (keyboard emulation for text UI) on all CompositeDevices
    echo "Loading gamepad profile on all devices..."
    
    # Get list of all CompositeDevices
    local devices=$(busctl tree org.shadowblip.InputPlumber 2>/dev/null | grep CompositeDevice | awk '{print $NF}')
    local loaded_count=0
    
    for device in $devices; do
        echo "  Loading profile on $device..."
        local max_retry=3
        local retry=0
        
        while [ $retry -lt $max_retry ]; do
            if busctl call org.shadowblip.InputPlumber \
                "$device" \
                org.shadowblip.Input.CompositeDevice \
                LoadProfilePath "s" /root/gamepad_profile.yaml &> /dev/null; then
                echo "  ✓ Profile loaded on $device"
                loaded_count=$((loaded_count + 1))
                break
            fi
            retry=$((retry + 1))
            [ $retry -lt $max_retry ] && sleep 1
        done
        
        if [ $retry -ge $max_retry ]; then
            echo "  ✗ Failed to load profile on $device"
        fi
    done
    
    if [ $loaded_count -gt 0 ]; then
        echo "Gamepad profile loaded on $loaded_count device(s)"
        return 0
    else
        echo "Warning: Failed to load gamepad profile on any device"
        echo "Controllers may still work with native support in graphical mode"
        return 1
    fi
}

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

copy_system_configs

# ===== Setup controller support before selecting installer =====
setup_controller_support

# ===== Graphical Installer with Smart Fallback =====
FAILURE_TRACKER="/tmp/installer-failures"
MIN_RUN_DURATION=15  # 如果运行<15秒，认为是启动失败
MAX_FAILURES=4       # 失败4次后自动降级到文本安装器

# 检查启动参数是否强制文本模式
if grep -q "installer=text" /proc/cmdline; then
    echo "检测到启动参数 installer=text，使用文本安装器"
    check_internet_connection
    [ "$OFFLINE_MODE" != "true" ] && check_and_update_install_script
    "$INSTALL_SCRIPT"
    exit $?
fi

# 检查图形安装器是否可用
if ! command -v gamescope &> /dev/null || \
   ! command -v python3 &> /dev/null || \
   ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null || \
   ! [ -f /usr/local/bin/installer-modular ]; then
    echo "图形安装器不可用，使用文本安装器"
    check_internet_connection
    [ "$OFFLINE_MODE" != "true" ] && check_and_update_install_script
    "$INSTALL_SCRIPT"
    exit $?
fi

# 检查失败次数
failure_count=0
[ -f "$FAILURE_TRACKER" ] && failure_count=$(wc -l < "$FAILURE_TRACKER")

# 达到失败阈值，自动降级
if [ "$failure_count" -ge "$MAX_FAILURES" ]; then
    echo "=========================================="
    echo "图形安装器已失败 ${failure_count} 次，自动降级到文本安装器"
    echo "=========================================="
    sleep 2
    rm -f "$FAILURE_TRACKER"
    check_internet_connection
    [ "$OFFLINE_MODE" != "true" ] && check_and_update_install_script
    "$INSTALL_SCRIPT"
    exit $?
fi

# 启动图形安装器
clear
echo "=========================================="
echo "启动图形化安装器 (尝试 $((failure_count + 1))/$((MAX_FAILURES + 1)))"
echo "=========================================="

# 清理旧的状态文件
rm -f /tmp/installer_success /tmp/installer_started

START_TIME=$SECONDS
/usr/local/bin/installer-modular "$@"
EXIT_CODE=$?
RUN_DURATION=$((SECONDS - START_TIME))

echo "图形安装器退出: 退出码=$EXIT_CODE, 运行时长=${RUN_DURATION}秒" >> /tmp/installer-launch.log

# 判断是否失败（多重检测）
IS_FAILURE=false
FAILURE_REASON=""

# 检查1: 状态文件（精确判断）
if [ -f /tmp/installer_started ]; then
    # Python 已启动
    if [ ! -f /tmp/installer_success ]; then
        # 启动了但没有标记成功 = 崩溃或异常
        IS_FAILURE=true
        FAILURE_REASON="启动后崩溃或异常退出（已启动但未正常结束）"
    fi
else
    # Python 未启动 = Socket 失败或 Gamescope 崩溃
    if [ "$EXIT_CODE" -ne 0 ]; then
        IS_FAILURE=true
        FAILURE_REASON="启动失败（Socket 超时或 Gamescope 崩溃）"
    fi
fi

# 检查2: 运行时长（兜底检查，防止状态文件未创建）
if [ "$IS_FAILURE" = false ] && [ "$RUN_DURATION" -lt "$MIN_RUN_DURATION" ] && [ "$EXIT_CODE" -ne 0 ]; then
    IS_FAILURE=true
    FAILURE_REASON="快速异常退出（运行时长<${MIN_RUN_DURATION}秒，退出码=$EXIT_CODE）"
fi

# 处理失败
if [ "$IS_FAILURE" = true ]; then
    echo "failure at $(date)" >> "$FAILURE_TRACKER"
    new_count=$(wc -l < "$FAILURE_TRACKER")
    
    echo "检测到失败: $FAILURE_REASON" >> /tmp/installer-launch.log
    echo "失败次数: ${new_count}/${MAX_FAILURES}" >> /tmp/installer-launch.log
    
    if [ "$new_count" -ge "$MAX_FAILURES" ]; then
        # 达到阈值，自动降级到文本安装器
        clear
        echo "=========================================="
        echo "图形安装器多次失败，切换到文本安装器"
        echo "=========================================="
        sleep 2
        rm -f "$FAILURE_TRACKER"
        check_internet_connection
        [ "$OFFLINE_MODE" != "true" ] && check_and_update_install_script
        "$INSTALL_SCRIPT"
        exit $?
    else
        # 还有重试机会，自动重试
        sleep 2
        exec "$0" "$@"  # 递归调用自己
    fi
else
    # 正常退出（成功或用户主动）
    rm -f "$FAILURE_TRACKER"
fi

# 清理状态文件
rm -f /tmp/installer_success /tmp/installer_started
