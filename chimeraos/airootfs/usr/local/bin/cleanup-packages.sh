#!/bin/bash
# Package cleanup script for ChimeraOS ISO
# This script removes unnecessary packages to reduce ISO size

set -e

# 日志记录函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a /tmp/package-cleanup.log
}

# 删除pacman锁文件以允许在hook中执行pacman操作
echo "Removing pacman database lock..."
rm -f /var/lib/pacman/db.lck

log "开始包清理过程..."

# 定义要卸载的包列表
# 这些是在最终ISO中不需要的包，但可能在构建过程中被作为依赖安装
PACKAGES_TO_REMOVE=(
    # 开发工具（如果不需要）
    "make"
    "gcc"
    "cmake"
    "autoconf"
    "automake"
    "pkg-config"
    
    "linux-headers"
    "linux-skchos-headers"
    "dkms"
    
    # 文档包（如果要减小体积）
    "man-db"
    "man-pages"
    "texinfo"
    
    # 某些语言包（根据需要保留）
    # "python-pip"
    # "python-setuptools"
    
    # 其他可能不需要的包
    "vi"  # 如果已经有vim或nano
)

# 定义绝对不能卸载的关键包（保护列表）
PROTECTED_PACKAGES=(
    "base"
    "linux-skchos" 
    "systemd"
    "networkmanager"
    "dialog"
    "frzr"
    "pikaur"
)

# 检查包是否存在且已安装
package_installed() {
    pacman -Qi "$1" &>/dev/null
}

# 检查包是否被其他包依赖
package_has_dependents() {
    local pkg="$1"
    local dependents=$(pactree -r "$pkg" 2>/dev/null | tail -n +2 | wc -l)
    [ "$dependents" -gt 0 ]
}

# 安全卸载包
safe_remove_package() {
    local pkg="$1"
    
    # 检查是否在保护列表中
    for protected in "${PROTECTED_PACKAGES[@]}"; do
        if [[ "$pkg" == "$protected" ]]; then
            log "跳过受保护的包: $pkg"
            return 0
        fi
    done
    
    # 检查包是否已安装
    if ! package_installed "$pkg"; then
        # log "包未安装，跳过: $pkg"
        return 0
    fi
    
    # 检查是否有其他包依赖此包
    # if package_has_dependents "$pkg"; then
    #     log "包被其他包依赖，跳过: $pkg"
    #     return 0
    # fi
    
    log "尝试卸载包: $pkg"
    if pacman -Rnsdd --noconfirm "$pkg"; then
        log "成功卸载: $pkg"
    else
        log "卸载失败: $pkg (可能有依赖问题)"
    fi
}

# 主清理流程
main() {
    log "开始卸载指定的包..."
    
    # 逐个处理要卸载的包
    for pkg in "${PACKAGES_TO_REMOVE[@]}"; do
        safe_remove_package "$pkg"
    done
    
    log "清理孤立包..."
    # 清理孤立包（没有被任何包依赖的包）
    orphans=$(pacman -Qtdq 2>/dev/null || true)
    if [[ -n "$orphans" ]]; then
        log "发现孤立包: $orphans"
        echo "$orphans" | xargs -r pacman -Rs --noconfirm 2>/dev/null || true
        log "孤立包清理完成"
    # else
    #     log "没有发现孤立包"
    fi
    
    log "清理包缓存..."
    # 清理包缓存以减小ISO体积
    pacman -Scc --noconfirm 2>/dev/null || true
    
    # 清理其他临时文件
    log "清理临时文件..."
    rm -rf /var/cache/pacman/pkg/*
    rm -rf /tmp/*
    rm -rf /var/tmp/*
    
    # 清理日志文件（可选）
    # truncate -s 0 /var/log/*.log 2>/dev/null || true
    
    log "包清理过程完成"
    
    # 显示最终的包统计
    total_packages=$(pacman -Q | wc -l)
    log "最终安装的包总数: $total_packages"
}

# 更简单可靠的方法：既然这个脚本是通过pacman hook调用的，
# 而pacman hook只在ISO构建过程中执行，那就直接运行
log "通过pacman hook调用，执行包清理"
main 