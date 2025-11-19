# 重试机制测试脚本

这些脚本用于测试 `install-init.sh` 和 `installer-modular` 的重试和失败处理机制。

## 文件说明

- **test-retry-mechanism.sh** - 核心测试脚本，模拟各种失败场景
- **run-all-tests.sh** - 运行所有测试场景的测试套件

## 测试场景

### 1. success - 立即成功（图形安装器）
模拟图形安装器第一次就成功启动和运行。

**预期结果**: ✅ 第1次尝试就成功，使用图形安装器

### 2. timeout_once - 超时一次后成功
模拟第一次 gamescope 启动超时（socket 无响应），第二次成功。

**预期结果**: ✅ 第1次失败，第2次成功，使用图形安装器

### 3. crash_once - 崩溃一次后成功
模拟第一次 Python 应用启动后崩溃（已创建 installer_started 但未创建 installer_success），第二次成功。

**预期结果**: ✅ 第1次失败（崩溃），第2次成功，使用图形安装器

### 4. always_fail - 图形安装器失败，降级到文本安装器
模拟图形安装器持续启动失败（gamescope socket 超时），达到最大重试次数后降级到文本安装器，文本安装器成功。

**预期结果**: ✅ 图形安装器失败2次 → 降级到文本安装器 → 成功

### 5. text_installer_fail - 图形和文本安装器都失败
模拟图形安装器失败后降级到文本安装器，但文本安装器也失败（如磁盘错误）。

**预期结果**: ❌ 图形安装器失败2次 → 降级到文本安装器 → 文本安装器也失败 → 完全失败

## 使用方法

### 运行单个测试场景

```bash
./test-retry-mechanism.sh <mode>
```

示例：
```bash
# 测试超时后重试成功
./test-retry-mechanism.sh timeout_once

# 测试总是失败的情况
./test-retry-mechanism.sh always_fail
```

### 运行所有测试

```bash
./run-all-tests.sh
```

这将依次运行所有5个测试场景并显示汇总结果。

## 配置参数

可以在 `test-retry-mechanism.sh` 中修改这些参数：

```bash
MIN_RUN_DURATION=15   # 最小运行时长（秒），低于此值认为异常退出
MAX_FAILURES=2        # 最大失败次数，超过后降级到文本安装器
```

## 失败检测逻辑

测试脚本实现了与 `install-init.sh` 相同的失败检测逻辑：

### 检测1: 状态文件检测
- ✅ 有 `installer_started` + 有 `installer_success` = 正常
- ❌ 有 `installer_started` + 无 `installer_success` = 启动后崩溃
- ❌ 无 `installer_started` + 退出码≠0 = Socket 超时或 gamescope 崩溃

### 检测2: 运行时长检测（兜底）
- ❌ 运行时长 < 15秒 + 退出码≠0 = 快速异常退出

## 输出说明

测试脚本会显示：
- 🔢 当前尝试次数
- 📊 模拟的失败场景
- ⏱️ 退出码和运行时长
- ✓/✗ 状态文件检测结果
- ❌/✅ 失败原因或成功标记
- 📈 失败计数器状态

## 实际行为对比

| 测试场景 | 图形安装器重试 | 文本安装器 | 最终结果 | 模拟总耗时 |
|---------|-------------|-----------|---------|----------|
| success | 1次 | 未使用 | ✅ 成功（图形） | ~5秒 |
| timeout_once | 2次 | 未使用 | ✅ 成功（图形） | ~9秒 |
| crash_once | 2次 | 未使用 | ✅ 成功（图形） | ~15秒 |
| always_fail | 2次 | 成功 | ✅ 成功（文本） | ~16秒 |
| text_installer_fail | 2次 | 失败 | ❌ 完全失败 | ~12秒 |

在实际环境中，每次尝试的超时时间是 25秒（GAMESCOPE_STARTUP_TIMEOUT），所以：
- **图形安装器成功**：取决于安装器实际运行时长
- **降级到文本安装器**：2次 × 25秒 = 50秒图形尝试 + 文本安装时间
- **完全失败**：50秒图形尝试 + 文本安装失败时间

## 清理

测试脚本会自动清理临时文件：
- `/tmp/test-installer-failures` - 失败计数器
- `/tmp/installer_started` - 启动标记
- `/tmp/installer_success` - 成功标记

## 注意事项

⚠️ 这些是**测试脚本**，不要在生产环境中运行。

实际的重试逻辑在：
- `skorionos/airootfs/root/install-init.sh` - 重试和降级逻辑
- `skorionos/airootfs/usr/local/bin/installer-modular` - 单次启动和超时检测

