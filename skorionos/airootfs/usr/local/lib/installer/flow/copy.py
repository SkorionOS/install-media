"""Shared installer copy — GTK and TUI both render these strings."""

from __future__ import annotations

from ..config import config

MIN_DISK_GB = config.min_disk_size

# --- Mode ---
MODE_TITLE = "选择安装类型"
MODE_TITLE_EXISTING = "检测到现有安装"
MODE_SUBTITLE = "请选择安装方式："
MODE_SUBTITLE_EXISTING = "磁盘 /dev/{disk} 上已有 frzr 安装。\n请选择操作："
MODE_REPAIR = "修复安装"
MODE_REPAIR_DESC = "保留用户数据，修复引导和系统文件"
MODE_FRESH = "全新安装"
MODE_FRESH_DESC = "格式化整个磁盘"
MODE_FRESH_EXISTING = "重新安装 (全新)"
MODE_FRESH_EXISTING_DESC = "格式化整个磁盘，删除所有数据"
MODE_DUAL = "双系统安装"
MODE_DUAL_DESC = "保留现有系统，与其他系统共存"
MODE_DUAL_EXISTING = "重新安装 (双系统)"
MODE_DUAL_EXISTING_DESC = "保留其他系统，与现有系统共存"

# --- Disk gates ---
DISK_TOO_SMALL_TITLE = "磁盘空间不足"
DISK_TOO_SMALL_MSG = "磁盘 {disk} 小于 {min_gb}GB，无法安装 SkorionOS。"
DISK_TOO_SMALL_DETAIL = (
    f"SkorionOS 需要至少 {MIN_DISK_GB}GB 的可用空间。\n请选择更大的磁盘。"
)

EXTERNAL_TITLE = "外部磁盘警告"
EXTERNAL_MSG = "磁盘 {disk} 似乎是外部设备（USB/SD卡等）。"
EXTERNAL_DETAILS = (
    "在外部磁盘上安装可能导致：\n"
    "• 系统性能不佳\n"
    "• 启动速度缓慢\n"
    "• 磁盘易损坏或丢失\n\n"
    "强烈建议安装到内置磁盘。\n是否仍要继续安装到此磁盘？"
)

INCOMPLETE_TITLE = "检测到不完整的 frzr 安装残留"
INCOMPLETE_MSG = "磁盘 /dev/{disk} 上有不完整的 frzr 分区。"
INCOMPLETE_DETAILS = (
    "这可能是之前安装失败的结果。\n"
    "建议清理残留分区后重新安装。\n\n"
    "是否清理残留分区？"
)

NO_SHRINK_PART_TITLE = "没有可调整的分区"
NO_SHRINK_PART_MSG = (
    f"没有找到可以操作的分区（需要 >= {MIN_DISK_GB}GB 的 ntfs/ext4/btrfs 分区）"
)

NETWORK_OFFLINE_TITLE = "网络连接已断开"
NETWORK_OFFLINE_MSG = "在线安装需要稳定的网络连接。"
NETWORK_OFFLINE_DETAIL = "请连接网络后重试，或选择本地安装。"

# --- Complete ---
COMPLETE_SUCCESS_TITLE = "安装完成"
COMPLETE_SUCCESS_SUMMARY = "SkorionOS 已成功安装到您的设备"
COMPLETE_CANCEL_TITLE = "安装已取消"
COMPLETE_CANCEL_SUMMARY = "安装已被取消"
COMPLETE_FAIL_TITLE = "安装失败"
COMPLETE_FAIL_SUMMARY = "安装过程中遇到错误"
UPLOAD_WORKING = "正在上传日志..."
UPLOAD_OK = "日志上传成功"
UPLOAD_FAIL = "日志上传失败"
UPLOAD_HINT = "您可以稍后手动上传: fpaste {log_file}"
UPLOAD_NONE = "暂无日志文件（未执行安装操作）"
UPLOAD_SKIPPED = "开发/模拟模式，跳过日志上传"
LOG_FILE_LINE = "日志文件: {log_file}"

BTN_BACK = "返回"
BTN_EXIT = "退出"
BTN_CONTINUE = "继续"
BTN_REBOOT = "重启"
BTN_SHUTDOWN = "关机"
BTN_SHELL = "打开命令行"
BTN_REINSTALL = "重新安装"
BTN_CLEANUP = "清理"

# --- Advanced ---
ADVANCED_TITLE = "高级安装选项"
ADVANCED_SUBTITLE = "选择需要启用的高级功能："
ADVANCED_ENABLE = "启用高级选项"
ADVANCED_CONTINUE = "继续安装"
ADVANCED_OPTIONS = (
    ("firmware_overrides", "使用固件覆盖", "覆盖系统 DSDT/EDID 固件", False),
    ("cdn", "CDN 加速", "使用 CDN 加速 GitHub 下载", False),
    ("fallback_url", "使用备用源 (推荐)", "使用 Gitee/Gitcode 镜像源", True),
    ("debug", "Debug 模式", "启用详细日志输出用于排错", False),
)
