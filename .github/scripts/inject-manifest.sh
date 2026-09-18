#!/bin/bash
# .github/scripts/inject-manifest.sh
#
# 向单个 AndroidManifest 文件幂等注入 MANAGE_EXTERNAL_STORAGE 权限。
# 被 patch-p4a.sh 和 p4a-patcher.sh 共用。
#
# 用法：
#   bash .github/scripts/inject-manifest.sh <manifest-file>
#
# 幂等规则：
#   - 文件不存在 / 不含 <manifest / 不含 <application → 直接跳过
#   - 已包含 MANAGE_EXTERNAL_STORAGE → 直接跳过
#   - 缺少 xmlns:tools → 自动补上
#   - 在 <application 之前插入 <uses-permission .../>
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

# 已经注入过：跳过
grep -q 'MANAGE_EXTERNAL_STORAGE' "$MF" 2>/dev/null && exit 0

# 补 xmlns:tools
if ! grep -q 'xmlns:tools=' "$MF" 2>/dev/null; then
    sed -i 's|xmlns:android="http://schemas.android.com/apk/res/android"|xmlns:android="http://schemas.android.com/apk/res/android" xmlns:tools="http://schemas.android.com/tools"|' "$MF" 2>/dev/null || true
fi

# 在 <application 前插入权限
sed -i 's|<application|<uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" tools:ignore="ScopedStorage" />\n    <application|' "$MF" 2>/dev/null || true

echo "[inject-manifest] 已注入权限到 $MF"
exit 0
