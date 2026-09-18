#!/bin/bash
# .github/scripts/patch-p4a.sh
#
# 处理 python-for-android 的克隆与补丁。
#
# 用法：
#   bash .github/scripts/patch-p4a.sh patch        # 克隆 p4a 到两个位置并打补丁
#   bash .github/scripts/patch-p4a.sh clean-cache  # 清理 buildozer 缓存
#
# 依赖环境变量（由 workflow 提供）：
#   GITHUB_WORKSPACE
#   TARGET_PYTHON
#   PY_TARBALL_MD5
#   PY_TARBALL_SHA256

set -euo pipefail

CMD="${1:-}"

if [ -z "$CMD" ]; then
    echo "用法: bash .github/scripts/patch-p4a.sh <patch|clean-cache>"
    exit 1
fi

# 兼容：如果环境变量缺失，给出清晰报错
: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE 未设置}"
: "${TARGET_PYTHON:?TARGET_PYTHON 未设置}"
: "${PY_TARBALL_MD5:?PY_TARBALL_MD5 未设置}"
: "${PY_TARBALL_SHA256:?PY_TARBALL_SHA256 未设置}"

# 本脚本同目录的 inject-manifest.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INJECT="$SCRIPT_DIR/inject-manifest.sh"

# ================================================================
# patch：克隆 p4a 到两个位置并打补丁
# ================================================================
if [ "$CMD" = "patch" ]; then

    P4A_DIR_A="$GITHUB_WORKSPACE/python-for-android"
    P4A_DIR_B="$GITHUB_WORKSPACE/.buildozer/android/platform/python-for-android"

    rm -rf "$P4A_DIR_A" "$GITHUB_WORKSPACE/.buildozer"
    mkdir -p "$(dirname "$P4A_DIR_B")"

    echo "======== Clone p4a 到位置 A ========"
    git clone -b develop --single-branch https://github.com/kivy/python-for-android.git "$P4A_DIR_A"

    echo "======== 复制到位置 B ========"
    cp -r "$P4A_DIR_A" "$P4A_DIR_B"

    for P4A_DIR in "$P4A_DIR_A" "$P4A_DIR_B"; do
        echo ""
        echo "============================================================"
        echo "======== 给 $P4A_DIR 打补丁 ========"
        echo "============================================================"
        cd "$P4A_DIR"

        # ---------- 1. recipe 版本修补 ----------
        for RECIPE_NAME in python3 hostpython3; do
            RECIPE_FILE="pythonforandroid/recipes/$RECIPE_NAME/__init__.py"
            echo "---- 修改 $RECIPE_FILE ----"

            sed -i -E "s/^([[:space:]]*version[[:space:]]*=[[:space:]]*)['\"]3\.[0-9]+\.[0-9]+['\"]/\1'${TARGET_PYTHON}'/" "$RECIPE_FILE"
            sed -i -E "s/^([[:space:]]*md5sum[[:space:]]*=[[:space:]]*)['\"][a-fA-F0-9]+['\"]/\1'${PY_TARBALL_MD5}'/" "$RECIPE_FILE"
            sed -i -E "s/^([[:space:]]*sha256[[:space:]]*=[[:space:]]*)['\"][a-fA-F0-9]+['\"]/\1'${PY_TARBALL_SHA256}'/" "$RECIPE_FILE"
            sed -i -E "s|/3\.14\.[0-9]+/Python-3\.14\.[0-9]+\.tar\.xz|/${TARGET_PYTHON}/Python-${TARGET_PYTHON}.tar.xz|g" "$RECIPE_FILE"

            grep -nE "version|md5sum|sha256|url" "$RECIPE_FILE" | head -20
        done

        # ---------- 2. JNI 修复：PythonActivity 静态块 ----------
        JAVA_FILE=$(find "$P4A_DIR" -name "PythonActivity.java" -type f 2>/dev/null | head -1)
        if [ -z "$JAVA_FILE" ]; then
            echo "警告：未找到 PythonActivity.java"
        else
            if ! grep -q "loadQt6CoreFirst" "$JAVA_FILE"; then
                sed -i '/^public class PythonActivity/a\
              /* loadQt6CoreFirst */\
              static {\
                  try {\
                      String abi = android.os.Build.SUPPORTED_ABIS[0];\
                      System.loadLibrary("Qt6Core_" + abi);\
                  } catch (Throwable t) {\
                      t.printStackTrace();\
                  }\
              }' "$JAVA_FILE"
                echo "已插入 Qt6Core 静态块"
            else
                echo "Qt6Core 静态块已存在，跳过"
            fi
        fi

        # ---------- 3. manifest 权限注入（初次尝试） ----------
        MANIFEST_FILES=$(find "$P4A_DIR" -type f \( -name "AndroidManifest*.xml" -o -name "AndroidManifest*.tmpl*" \) 2>/dev/null || true)
        echo "---- 发现 manifest 文件 ----"
        echo "$MANIFEST_FILES"
        echo "$MANIFEST_FILES" | while IFS= read -r mf; do
            [ -f "$mf" ] || continue
            bash "$INJECT" "$mf" || true
        done

        # 最终检查
        grep -nE "^[[:space:]]*version[[:space:]]*=" "pythonforandroid/recipes/python3/__init__.py" || true
    done

    echo "======== 最终确认 ========"
    echo "位置 A p4a: $(test -d "$P4A_DIR_A" && echo 存在 || echo 不存在)"
    echo "位置 B p4a: $(test -d "$P4A_DIR_B" && echo 存在 || echo 不存在)"
    exit 0
fi

# ================================================================
# clean-cache：清理 buildozer 构建缓存
# ================================================================
if [ "$CMD" = "clean-cache" ]; then
    PLATFORM_DIR="$GITHUB_WORKSPACE/.buildozer/android/platform"

    find "$PLATFORM_DIR" -maxdepth 1 -type d -name "build-*" -exec rm -rf {} + 2>/dev/null || true
    rm -rf "$PLATFORM_DIR/python-for-android/dists" 2>/dev/null || true
    rm -rf "$PLATFORM_DIR/python-for-android/build" 2>/dev/null || true
    rm -rf "$PLATFORM_DIR/python-for-android/.buildozer" 2>/dev/null || true

    echo "======== 确认 p4a recipe 状态 ========"
    grep -nE "^[[:space:]]*version[[:space:]]*=" "$PLATFORM_DIR/python-for-android/pythonforandroid/recipes/python3/__init__.py" || true
    exit 0
fi

echo "未知子命令: $CMD"
exit 1
