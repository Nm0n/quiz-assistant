#!/bin/bash
# .github/scripts/patch-buildozer-spec.sh
#
# 修改 buildozer 自带的 default.spec，让 buildozer 使用我们预克隆并打过补丁的 p4a。
#
# 依赖环境变量：
#   VIRTUAL_ENV           venv 路径（由 setup-env.sh venv 写入）
#   GITHUB_WORKSPACE

set -euo pipefail

# shellcheck disable=SC1091
source "$HOME/venv/bin/activate"

: "${VIRTUAL_ENV:?VIRTUAL_ENV 未设置，venv 未激活}"
: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE 未设置}"

DEFAULT_SPEC="$VIRTUAL_ENV/lib/python3.11/site-packages/buildozer/default.spec"

if [ ! -f "$DEFAULT_SPEC" ]; then
    echo "!!! 找不到 default.spec: $DEFAULT_SPEC"
    find "$VIRTUAL_ENV" -name "default.spec" 2>/dev/null || true
    exit 1
fi

P4A_DIR_B="$GITHUB_WORKSPACE/.buildozer/android/platform/python-for-android"

if grep -q "^p4a.source_dir" "$DEFAULT_SPEC"; then
    sed -i "s|^p4a.source_dir.*|p4a.source_dir = ${P4A_DIR_B}|" "$DEFAULT_SPEC"
else
    sed -i "/^\[buildozer\]/a p4a.source_dir = ${P4A_DIR_B}" "$DEFAULT_SPEC"
fi

grep -A 20 "^\[buildozer\]" "$DEFAULT_SPEC" || true
