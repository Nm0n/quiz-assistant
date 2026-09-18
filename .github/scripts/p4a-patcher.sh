#!/bin/bash
# .github/scripts/p4a-patcher.sh
#
# 后台常驻 patcher：持续监控 python-for-android 的 recipe 与 manifest，
# 一旦 buildozer / p4a 重新 clone 或重新生成文件，就立即重新打补丁。
#
# 由 workflow 用 `nohup bash .github/scripts/p4a-patcher.sh &` 启动，
# PID 写到 /tmp/patcher.pid。
#
# 输出日志：/tmp/patcher.log
#
# 依赖环境变量：
#   GITHUB_WORKSPACE
#   TARGET_PYTHON
#   PY_TARBALL_MD5
#   PY_TARBALL_SHA256
#
# 注意：本脚本故意不使用 `set -e`，
#       因为它在后台循环中长期运行，任何 grep/find 非零退出都不应终止进程。

set -uo pipefail

: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE 未设置}"
: "${TARGET_PYTHON:?TARGET_PYTHON 未设置}"
: "${PY_TARBALL_MD5:?PY_TARBALL_MD5 未设置}"
: "${PY_TARBALL_SHA256:?PY_TARBALL_SHA256 未设置}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INJECT="$SCRIPT_DIR/inject-manifest.sh"

LOG="/tmp/patcher.log"
echo "[Patcher] 启动于 $(date)" > "$LOG"
echo "[Patcher] GITHUB_WORKSPACE=$GITHUB_WORKSPACE" >> "$LOG"
echo "[Patcher] TARGET_PYTHON=$TARGET_PYTHON" >> "$LOG"
echo "[Patcher] INJECT=$INJECT" >> "$LOG"

# ----------------------------------------------------------------
# recipe 修补：把 3.14 改回 TARGET_PYTHON，并覆盖 md5/sha256/url
# ----------------------------------------------------------------
patch_recipe() {
    local RECIPE_FILE="$1"
    [ -f "$RECIPE_FILE" ] || return 0
    grep -qE "3\.14" "$RECIPE_FILE" || return 0

    echo "[Patcher] $(date) 修补 recipe: $RECIPE_FILE" >> "$LOG"

    sed -i -E "s/version = '3\.14\.[0-9]+'/version = '${TARGET_PYTHON}'/" "$RECIPE_FILE" 2>/dev/null || true
    sed -i -E "s/version = \"3\.14\.[0-9]+\"/version = '${TARGET_PYTHON}'/" "$RECIPE_FILE" 2>/dev/null || true
    sed -i -E "s/md5sum = '[a-fA-F0-9]+'/md5sum = '${PY_TARBALL_MD5}'/" "$RECIPE_FILE" 2>/dev/null || true
    sed -i -E "s/sha256 = '[a-fA-F0-9]+'/sha256 = '${PY_TARBALL_SHA256}'/" "$RECIPE_FILE" 2>/dev/null || true
    sed -i -E "s|3\.14\.[0-9]+/Python-3\.14\.[0-9]+\.tar\.xz|${TARGET_PYTHON}/Python-${TARGET_PYTHON}.tar.xz|g" "$RECIPE_FILE" 2>/dev/null || true
}

# ----------------------------------------------------------------
# 扫描单个 p4a 目录：recipe + manifest
# ----------------------------------------------------------------
patch_p4a_dir() {
    local P4A_DIR="$1"
    [ -d "$P4A_DIR" ] || return 0

    # recipe 修补
    local RECIPE_REL
    for RECIPE_REL in \
        "pythonforandroid/recipes/python3/__init__.py" \
        "pythonforandroid/recipes/hostpython3/__init__.py" ; do
        patch_recipe "$P4A_DIR/$RECIPE_REL"
    done

    # manifest 注入
    local MF
    while IFS= read -r MF; do
        [ -n "$MF" ] || continue
        bash "$INJECT" "$MF" >> "$LOG" 2>&1 || true
    done < <(find "$P4A_DIR" -type f \( -name "AndroidManifest*.xml" -o -name "AndroidManifest*.tmpl*" \) 2>/dev/null)
}

# ----------------------------------------------------------------
# 扫描 buildozer dist 目录下的 manifest
# ----------------------------------------------------------------
patch_dist_dir() {
    local DIST_DIR="$1"
    [ -d "$DIST_DIR" ] || return 0

    local MF
    while IFS= read -r MF; do
        [ -n "$MF" ] || continue
        bash "$INJECT" "$MF" >> "$LOG" 2>&1 || true
    done < <(find "$DIST_DIR" -type f -name "AndroidManifest*.xml" 2>/dev/null)
}

# ----------------------------------------------------------------
# 主循环
# ----------------------------------------------------------------
while true; do
    # 1. 候选 p4a 目录
    for P4A_DIR in \
        "$GITHUB_WORKSPACE/.buildozer/android/platform/python-for-android" \
        "$GITHUB_WORKSPACE/python-for-android" \
        "$HOME/.buildozer/android/platform/python-for-android" ; do
        patch_p4a_dir "$P4A_DIR"
    done

    # 2. buildozer dist 目录
    for DIST_DIR in \
        "$HOME/.buildozer/android/platform/build-arm64-v8a/dists" \
        "$GITHUB_WORKSPACE/.buildozer/android/platform/build-arm64-v8a/dists" ; do
        patch_dist_dir "$DIST_DIR"
    done

    sleep 1
done
