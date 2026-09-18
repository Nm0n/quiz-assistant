#!/bin/bash
# .github/scripts/verify-apk.sh
#
# 验证 APK 内容：
#   - libpython3.11.so 是否存在（而非 3.14）
#   - MANAGE_EXTERNAL_STORAGE 是否注入（优先 aapt2，降级 strings）
#   - libc++_shared.so 是否包含 std::pmr 符号
#
# 本步骤仅做诊断，不因失败而中断构建。内部所有命令均带兜底。

set -uo pipefail

APK=$(find dist -name "*.apk" 2>/dev/null | head -1)
if [ -z "$APK" ]; then
    echo "没有找到 APK，跳过验证"
    exit 0
fi

echo "检查 APK: $APK"
echo "=== lib/arm64-v8a/ 中的 libpython 和 libshiboken ==="
unzip -l "$APK" | grep -E "libpython|libshiboken|libc\+\+" || true

echo ""
echo "=== 关键判定：libpython 版本 ==="
if unzip -l "$APK" | grep -q "libpython3.11.so"; then
    echo "✅ APK 中包含 libpython3.11.so"
elif unzip -l "$APK" | grep -q "libpython3.14.so"; then
    echo "❌ APK 中仍然是 libpython3.14.so —— p4a 补丁没有生效"
else
    echo "❌ APK 中没有任何 libpython3.x.so"
fi

echo ""
echo "=== 关键判定：MANAGE_EXTERNAL_STORAGE 权限 ==="
AAPT2=$(find "$ANDROID_HOME/build-tools" -name "aapt2" 2>/dev/null | head -1)
if [ -n "$AAPT2" ]; then
    echo "使用 aapt2 检查权限..."
    "$AAPT2" dump permissions "$APK" 2>/dev/null | grep -i "MANAGE_EXTERNAL_STORAGE" && \
      echo "✅ aapt2 确认权限已注入" || \
      echo "❌ aapt2 未发现 MANAGE_EXTERNAL_STORAGE"
else
    echo "未找到 aapt2，改用 strings 检查..."
    unzip -p "$APK" AndroidManifest.xml 2>/dev/null | strings | grep -i "MANAGE_EXTERNAL_STORAGE" && \
      echo "✅ strings 确认权限已注入" || \
      echo "❌ strings 未发现 MANAGE_EXTERNAL_STORAGE"
fi

echo ""
echo "=== 检查 libc++_shared.so 是否包含 std::pmr 符号 ==="
mkdir -p /tmp/apkcheck
unzip -o "$APK" "lib/arm64-v8a/libc++_shared.so" -d /tmp/apkcheck 2>/dev/null || true
if [ -f /tmp/apkcheck/lib/arm64-v8a/libc++_shared.so ]; then
    READELF=$(find "$ANDROID_HOME/ndk/${ANDROID_NDK_VERSION}/toolchains/llvm/prebuilt/linux-x86_64/bin" -name "llvm-readelf" 2>/dev/null | head -1)
    if [ -n "$READELF" ]; then
        "$READELF" -sW /tmp/apkcheck/lib/arm64-v8a/libc++_shared.so | grep -i "monotonic_buffer_resource" && echo "✅ 找到 pmr 符号" || echo "❌ 未找到 pmr 符号"
    fi
fi

exit 0
