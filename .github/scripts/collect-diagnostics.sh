#!/bin/bash
# .github/scripts/collect-diagnostics.sh
#
# 构建后的诊断、patcher 停止、APK 收集、项目根目录清单。
#
# 用法：
#   bash .github/scripts/collect-diagnostics.sh post-deploy
#   bash .github/scripts/collect-diagnostics.sh stop-patcher
#   bash .github/scripts/collect-diagnostics.sh collect-apk
#   bash .github/scripts/collect-diagnostics.sh list-root
#
# 本脚本内所有命令均为诊断性质，任何失败都不应中断构建，
# 因此使用 `set -uo pipefail` 但不使用 `set -e`，
# 并在各处带 `|| true` / `|| echo` 兜底。

set -uo pipefail

CMD="${1:-}"
if [ -z "$CMD" ]; then
    echo "用法: bash .github/scripts/collect-diagnostics.sh <post-deploy|stop-patcher|collect-apk|list-root>"
    exit 1
fi

# ================================================================
# post-deploy：构建后诊断
# ================================================================
if [ "$CMD" = "post-deploy" ]; then
    echo "======== Patcher 日志 ========"
    cat /tmp/patcher.log || echo "无 patcher 日志"

    echo "======== deploy 后：位置 A recipe ========"
    grep -nE "^[[:space:]]*version[[:space:]]*=" "$GITHUB_WORKSPACE/python-for-android/pythonforandroid/recipes/python3/__init__.py" 2>/dev/null || echo "位置 A 不存在"

    echo "======== deploy 后：位置 B recipe ========"
    grep -nE "^[[:space:]]*version[[:space:]]*=" "$GITHUB_WORKSPACE/.buildozer/android/platform/python-for-android/pythonforandroid/recipes/python3/__init__.py" 2>/dev/null || echo "位置 B 不存在"

    echo "======== 查找所有 python-for-android 目录 ========"
    find / -type d -name "python-for-android" 2>/dev/null | head -20 || true

    echo "======== 查找所有 libpython3.14.so ========"
    find / -name "libpython3.14.so" 2>/dev/null | head -20 || true

    echo "======== 查找所有 libpython3.11.so ========"
    find / -name "libpython3.11.so" 2>/dev/null | head -20 || true

    echo "======== 查找所有 AndroidManifest 模板 ========"
    find / -name "AndroidManifest*.xml" 2>/dev/null | head -40 || true

    echo "======== 检查 manifest 里的 MANAGE_EXTERNAL_STORAGE ========"
    for mf in $(find / -name "AndroidManifest*.xml" 2>/dev/null | head -40); do
        if grep -q "MANAGE_EXTERNAL_STORAGE" "$mf" 2>/dev/null; then
            echo "✅ $mf 包含权限声明"
        fi
    done

    if [ -f "$GITHUB_WORKSPACE/build.log" ]; then
        echo "======== build.log 中 p4a 相关行 ========"
        grep -nE "python-for-android|p4a|buildozer|Cloning|3\.14|3\.11|MANAGE_EXTERNAL" "$GITHUB_WORKSPACE/build.log" | head -80 || true

        echo "======== build.log 末尾 50 行 ========"
        tail -50 "$GITHUB_WORKSPACE/build.log" || true
    fi
    exit 0
fi

# ================================================================
# stop-patcher：停止后台 patcher
# ================================================================
if [ "$CMD" = "stop-patcher" ]; then
    if [ -f /tmp/patcher.pid ]; then
        PID=$(cat /tmp/patcher.pid)
        kill "$PID" 2>/dev/null || true
        echo "已停止 Patcher PID: $PID"
    fi
    echo "======== 最终 Patcher 日志 ========"
    cat /tmp/patcher.log || echo "无 patcher 日志"
    exit 0
fi

# ================================================================
# collect-apk：收集 APK 到 dist/
# ================================================================
if [ "$CMD" = "collect-apk" ]; then
    mkdir -p dist
    find . -type f -name "*.apk" \
        -not -path "./dist/*" \
        -not -path "./.buildozer/*" \
        -not -path "./python-for-android/*" \
        -exec cp {} dist/ \; 2>/dev/null || true
    echo "=== dist/ 目录内容 ==="
    ls -lh dist/ || echo "dist/ 目录为空"
    exit 0
fi

# ================================================================
# list-root：项目根目录文件清单
# ================================================================
if [ "$CMD" = "list-root" ]; then
    echo "=== 项目根目录文件清单 ==="
    ls -la
    echo "=== 查找所有 APK 文件 ==="
    find . -type f -name "*.apk" 2>/dev/null || echo "未找到任何 APK 文件"
    exit 0
fi

echo "未知子命令: $CMD"
exit 1
