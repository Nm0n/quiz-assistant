#!/bin/bash
# .github/scripts/inject-manifest.sh
#
# 向单个 AndroidManifest 文件幂等注入：
#   1. MANAGE_EXTERNAL_STORAGE 权限
#   2. PythonActivity 的防重启属性（launchMode / alwaysRetainTaskState / configChanges）
# 被 patch-p4a.sh 和 p4a-patcher.sh 共用。
#
# 用法：
#   bash .github/scripts/inject-manifest.sh <manifest-file>
#
# 幂等规则：
#   - 文件不存在 / 不含 <manifest / 不含 <application → 直接跳过
#   - 权限：已包含 MANAGE_EXTERNAL_STORAGE → 跳过权限注入
#   - Activity：已包含 android:launchMode="singleTask" → 跳过属性注入
#   - 缺少 xmlns:tools → 自动补上
#   - 在 <application 之前插入 <uses-permission .../>
#   - 在 PythonActivity 的 android:name 属性后追加防重启属性
#
# 注意：本脚本故意不使用 `set -e`，因为它在 patcher 后台循环中被频繁调用，
#       任何 sed/grep 非零退出都不应中断流程。所有命令都带 `|| true` 兜底。

set -uo pipefail

MF="${1:-}"

if [ -z "$MF" ]; then
    echo "[inject-manifest] 缺少参数：manifest 文件路径"
    exit 1
fi

# 文件不存在：静默跳过
[ -f "$MF" ] || exit 0

# 必须包含 <manifest 和 <application，否则不是有效的 manifest
grep -q '<manifest' "$MF" 2>/dev/null || exit 0
grep -q '<application' "$MF" 2>/dev/null || exit 0

# ================================================================
# 1. 注入 MANAGE_EXTERNAL_STORAGE 权限
# ================================================================
if ! grep -q 'MANAGE_EXTERNAL_STORAGE' "$MF" 2>/dev/null; then

    # 补 xmlns:tools
    if ! grep -q 'xmlns:tools=' "$MF" 2>/dev/null; then
        sed -i 's|xmlns:android="http://schemas.android.com/apk/res/android"|xmlns:android="http://schemas.android.com/apk/res/android" xmlns:tools="http://schemas.android.com/tools"|' "$MF" 2>/dev/null || true
    fi

    # 在 <application 前插入权限
    sed -i 's|<application|<uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" tools:ignore="ScopedStorage" />\n    <application|' "$MF" 2>/dev/null || true

    echo "[inject-manifest] 已注入权限到 $MF"
else
    echo "[inject-manifest] 权限已存在，跳过：$MF"
fi

# ================================================================
# 2. 为 PythonActivity 注入防重启属性
# ================================================================
# 目标：阻止系统在文件选择器返回时销毁并重建 Activity，
#       从而保住 Qt 的事件循环和 QML 回调链。
#
# 属性说明：
#   launchMode="singleTask"        → 系统复用已有实例，不创建新的
#   alwaysRetainTaskState="true"   → 尽量保留任务栈状态，不被清理
#   configChanges="..."            → 声明 Activity 自己处理这些配置变化，
#                                    避免系统因此销毁重建 Activity
#
# 幂等标记：android:launchMode="singleTask"

if grep -q 'android:launchMode="singleTask"' "$MF" 2>/dev/null; then
    echo "[inject-manifest] 防重启属性已存在，跳过：$MF"
elif ! grep -q 'android:name="org.kivy.android.PythonActivity"' "$MF" 2>/dev/null; then
    echo "[inject-manifest] 未找到 PythonActivity 声明，跳过属性注入：$MF"
else
    # 用 # 作为 sed 分隔符，避免与属性值里的 | 冲突
    sed -i 's#android:name="org.kivy.android.PythonActivity"#android:name="org.kivy.android.PythonActivity" android:launchMode="singleTask" android:alwaysRetainTaskState="true" android:configChanges="orientation|screenSize|keyboardHidden|screenLayout|smallestScreenSize|uiMode|density"#' "$MF" 2>/dev/null || true
    echo "[inject-manifest] 已注入防重启属性到 $MF"
fi

exit 0
