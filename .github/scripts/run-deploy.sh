#!/bin/bash
# .github/scripts/run-deploy.sh
#
# 运行 pyside6-android-deploy，并把完整输出 tee 到 build.log。
# 保留 pyside6-android-deploy 的退出码作为本脚本退出码。
#
# 依赖环境变量：
#   PYSIDE_VERSION
#   ANDROID_NDK_HOME
#   ANDROID_HOME

set -euo pipefail

# shellcheck disable=SC1091
source "$HOME/venv/bin/activate"

echo "======== 环境检查 ========"
echo "VIRTUAL_ENV=$VIRTUAL_ENV"
which python
which pyside6-android-deploy
echo "JAVA_HOME=$JAVA_HOME"
java -version
pip show PySide6 | grep -E "Version|Location" || true
echo "ANDROID_NDK_HOME=$ANDROID_NDK_HOME"
echo "将传入 --ndk-path: $ANDROID_NDK_HOME"

WHEEL_PYSIDE="wheels/PySide6-${PYSIDE_VERSION}-${PYSIDE_VERSION}-cp311-cp311-android_aarch64.whl"
WHEEL_SHIBOKEN="wheels/shiboken6-${PYSIDE_VERSION}-${PYSIDE_VERSION}-cp311-cp311-android_aarch64.whl"
ls -lh "$WHEEL_PYSIDE" "$WHEEL_SHIBOKEN"

set +e
pyside6-android-deploy \
  --config-file pysidedeploy.spec \
  --wheel-pyside "$WHEEL_PYSIDE" \
  --wheel-shiboken "$WHEEL_SHIBOKEN" \
  --ndk-path "$ANDROID_NDK_HOME" \
  --sdk-path "$ANDROID_HOME" \
  2>&1 | tee build.log
EXIT_CODE=${PIPESTATUS[0]}
set -e
echo "pyside6-android-deploy 退出码: $EXIT_CODE"
exit $EXIT_CODE
