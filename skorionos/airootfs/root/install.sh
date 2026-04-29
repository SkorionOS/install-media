#!/bin/bash
# SkorionOS Installer - Manual mode selector
# Usage: ./install.sh

check_gui_available() {
    if ! command -v gamescope &> /dev/null; then
        echo "gamescope 未安装"; return 1
    elif ! command -v python3 &> /dev/null; then
        echo "python3 未安装"; return 1
    elif ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
        echo "GTK4/Adwaita 依赖缺失"; return 1
    elif ! [ -f /usr/local/bin/installer-modular ]; then
        echo "installer-modular 不存在"; return 1
    fi
    return 0
}

GUI_UNAVAIL_REASON=$(check_gui_available)
GUI_AVAILABLE=$?

echo "=========================================="
echo "  SkorionOS 安装器"
echo "=========================================="
echo ""

if [ "$GUI_AVAILABLE" -eq 0 ]; then
    echo "  1) 自动（优先图形，失败回退文本）"
    echo "  2) 图形安装器"
    echo "  3) 文本安装器"
else
    echo "  [!] 图形安装器不可用：${GUI_UNAVAIL_REASON}"
    echo ""
    echo "  1) 自动（将直接使用文本安装器）"
    echo "  3) 文本安装器"
fi

echo ""
read -r -p "请输入选项 [1/2/3]: " choice

case "$choice" in
    1)
        exec "$HOME/install-init.sh"
        ;;
    2)
        if [ "$GUI_AVAILABLE" -eq 0 ]; then
            exec /usr/local/bin/installer-modular "$@"
        else
            echo "图形安装器不可用：${GUI_UNAVAIL_REASON}"
            exit 1
        fi
        ;;
    3)
        exec "$HOME/installer-text.sh"
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac
