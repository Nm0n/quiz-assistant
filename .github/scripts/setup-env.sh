#!/bin/bash
# .github/scripts/setup-env.sh
#
# 环境准备脚本，由 build-apk.yml 按子命令调用。
# 所有环境变量从 workflow 的 env 段传入，不硬编码。
#
# 用法：
#   bash .github/scripts/setup-env.sh <子命令>
#
# 子命令：
#   venv             创建并激活 venv，写入 GITHUB_ENV / GITHUB_PATH
#   verify-java      验证 JAVA_HOME 和 java 版本
#   cmdline-tools    手动安装 Android cmdline-tools
#   jaxb             向 sdkmanager 注入 JAXB jar
#   symlinks         创建 legacy sdkmanager / avdmanager 软链接
#   verify-sdkmanager 验证 sdkmanager 可用
#   sdk-components   安装 platform-tools / platforms / build-tools
#   ndk              安装 NDK r27c
#   export-ndk       导出 NDK 相关环境变量到 GITHUB_ENV
#   system-deps      安装系统依赖
#   pyside           在 venv 中安装 PySide6 及部署工具
#   wheels           下载 Android aarch64 wheel
#   sanity-check     检查项目必要文件 / 目录
#   python-checksum  下载 Python 源码包并计算 md5 / sha256

set -euo pipefail

CMD="${1:-}"

if [ -z "$CMD" ]; then
    echo "用法: bash .github/scripts/setup-env.sh <子命令>"
    exit 1
fi

# ================================================================
# venv
# ================================================================
if [ "$CMD" = "venv" ]; then
    python -m venv "$HOME/venv"
    echo "VIRTUAL_ENV=$HOME/venv" >> "$GITHUB_ENV"
    echo "$HOME/venv/bin" >> "$GITHUB_PATH"
    # shellcheck disable=SC1091
    source "$HOME/venv/bin/activate"
    python --version
    which python
    pip --version
    exit 0
fi

# ================================================================
# verify-java
# ================================================================
if [ "$CMD" = "verify-java" ]; then
    echo "JAVA_HOME=$JAVA_HOME"
    java -version
    exit 0
fi

# ================================================================
# cmdline-tools
# ================================================================
if [ "$CMD" = "cmdline-tools" ]; then
    sudo mkdir -p "$ANDROID_HOME"
    sudo chown -R "$USER:$USER" "$ANDROID_HOME"
    echo "ANDROID_HOME=$ANDROID_HOME" >> "$GITHUB_ENV"

    cd /tmp
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-12266719_latest.zip -O cmdline-tools.zip
    unzip -q cmdline-tools.zip

    rm -rf "$ANDROID_HOME/cmdline-tools"
    mkdir -p "$ANDROID_HOME/cmdline-tools"
    mv cmdline-tools "$ANDROID_HOME/cmdline-tools/latest"

    echo "=== lib 目录里的 JAXB jar ==="
    ls "$ANDROID_HOME/cmdline-tools/latest/lib/" | grep -i "jaxb" || echo "!!! JAXB 未找到，稍后注入 !!!"
    exit 0
fi

# ================================================================
# jaxb
# ================================================================
if [ "$CMD" = "jaxb" ]; then
    SDKMGR="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
    LIBDIR="$ANDROID_HOME/cmdline-tools/latest/lib"

    mkdir -p "$LIBDIR"
    cd "$LIBDIR"
    wget -q https://repo1.maven.org/maven2/javax/xml/bind/jaxb-api/2.3.1/jaxb-api-2.3.1.jar
    wget -q https://repo1.maven.org/maven2/com/sun/xml/bind/jaxb-impl/2.3.1/jaxb-impl-2.3.1.jar
    wget -q https://repo1.maven.org/maven2/org/glassfish/jaxb/jaxb-core/2.3.0/jaxb-core-2.3.0.jar
    wget -q https://repo1.maven.org/maven2/javax/activation/javax.activation-api/1.2.0/javax.activation-api-1.2.0.jar

    if ! grep -q "jaxb-api-2.3.1" "$SDKMGR"; then
        sed -i "s|^CLASSPATH=\"|CLASSPATH=\"$LIBDIR/jaxb-api-2.3.1.jar:$LIBDIR/jaxb-impl-2.3.1.jar:$LIBDIR/jaxb-core-2.3.0.jar:$LIBDIR/javax.activation-api-1.2.0.jar:|" "$SDKMGR"
    fi

    echo "=== 修改后 CLASSPATH ==="
    grep -n "CLASSPATH" "$SDKMGR" || true
    exit 0
fi

# ================================================================
# symlinks
# ================================================================
if [ "$CMD" = "symlinks" ]; then
    mkdir -p "$ANDROID_HOME/tools/bin"
    mkdir -p "$ANDROID_HOME/cmdline-tools/bin"
    ln -sf "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "$ANDROID_HOME/tools/bin/sdkmanager"
    ln -sf "$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager" "$ANDROID_HOME/tools/bin/avdmanager"
    ln -sf "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "$ANDROID_HOME/cmdline-tools/bin/sdkmanager"
    ln -sf "$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager" "$ANDROID_HOME/cmdline-tools/bin/avdmanager"

    echo "$ANDROID_HOME/cmdline-tools/latest/bin" >> "$GITHUB_PATH"
    echo "$ANDROID_HOME/platform-tools" >> "$GITHUB_PATH"
    echo "$ANDROID_HOME/tools/bin" >> "$GITHUB_PATH"
    exit 0
fi

# ================================================================
# verify-sdkmanager
# ================================================================
if [ "$CMD" = "verify-sdkmanager" ]; then
    which sdkmanager
    sdkmanager --version
    exit 0
fi

# ================================================================
# sdk-components
# ================================================================
if [ "$CMD" = "sdk-components" ]; then
    yes | sdkmanager --install \
        "platform-tools" \
        "platforms;android-${ANDROID_SDK_VERSION}" \
        "build-tools;${ANDROID_BUILD_TOOLS}" || true
    yes | sdkmanager --licenses || true
    exit 0
fi

# ================================================================
# ndk
# ================================================================
if [ "$CMD" = "ndk" ]; then
    yes | sdkmanager --install "ndk;${ANDROID_NDK_VERSION}" || true
    test -d "$ANDROID_HOME/ndk/${ANDROID_NDK_VERSION}" || (echo "NDK 安装失败" && exit 1)
    echo "NDK r27c 已安装"
    ls "$ANDROID_HOME/ndk/${ANDROID_NDK_VERSION}/" | head -20
    exit 0
fi

# ================================================================
# export-ndk
# ================================================================
if [ "$CMD" = "export-ndk" ]; then
    echo "ANDROID_NDK_HOME=$ANDROID_HOME/ndk/${ANDROID_NDK_VERSION}" >> "$GITHUB_ENV"
    echo "ANDROID_NDK_ROOT=$ANDROID_HOME/ndk/${ANDROID_NDK_VERSION}" >> "$GITHUB_ENV"
    echo "ANDROID_NDK_PATH=$ANDROID_HOME/ndk/${ANDROID_NDK_VERSION}" >> "$GITHUB_ENV"
    echo "ANDROID_NDK_HOME=$ANDROID_NDK_HOME"
    echo "ANDROID_NDK_ROOT=$ANDROID_NDK_ROOT"
    exit 0
fi

# ================================================================
# system-deps
# ================================================================
if [ "$CMD" = "system-deps" ]; then
    sudo apt-get update
    sudo apt-get install -y \
        ant autoconf automake autopoint ccache cmake \
        g++ gcc git lbzip2 libffi-dev libltdl-dev libtool \
        libssl-dev make patch patchelf pkg-config \
        python3 python3-dev python3-pip python3-venv \
        unzip wget zip
    exit 0
fi

# ================================================================
# pyside
# ================================================================
if [ "$CMD" = "pyside" ]; then
    # shellcheck disable=SC1091
    source "$HOME/venv/bin/activate"
    which python
    which pip
    python -m pip install --upgrade pip
    pip install "PySide6==${PYSIDE_VERSION}"
    pip install "shiboken6==${PYSIDE_VERSION}"
    pip install packaging jinja2 pkginfo tqdm
    pip install buildozer cython virtualenv
    pip list | grep -i -E "pyside|shiboken|buildozer"
    which pyside6-android-deploy
    exit 0
fi

# ================================================================
# wheels
# ================================================================
if [ "$CMD" = "wheels" ]; then
    mkdir -p wheels
    wget -q --show-progress \
        "https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-${PYSIDE_VERSION}-${PYSIDE_VERSION}-cp311-cp311-android_aarch64.whl" \
        -O "wheels/PySide6-${PYSIDE_VERSION}-${PYSIDE_VERSION}-cp311-cp311-android_aarch64.whl"
    wget -q --show-progress \
        "https://download.qt.io/official_releases/QtForPython/shiboken6/shiboken6-${PYSIDE_VERSION}-${PYSIDE_VERSION}-cp311-cp311-android_aarch64.whl" \
        -O "wheels/shiboken6-${PYSIDE_VERSION}-${PYSIDE_VERSION}-cp311-cp311-android_aarch64.whl"
    ls -lh wheels/
    exit 0
fi

# ================================================================
# sanity-check
# ================================================================
if [ "$CMD" = "sanity-check" ]; then
    test -f main.py            || (echo "缺少 main.py" && exit 1)
    test -f pysidedeploy.spec  || (echo "缺少 pysidedeploy.spec" && exit 1)
    test -d core               || (echo "缺少 core/" && exit 1)
    test -d qml                || (echo "缺少 qml/" && exit 1)
    test -f qml/main.qml       || (echo "缺少 qml/main.qml" && exit 1)
    exit 0
fi

# ================================================================
# python-checksum
# ================================================================
if [ "$CMD" = "python-checksum" ]; then
    cd /tmp
    wget -q "https://www.python.org/ftp/python/${TARGET_PYTHON}/Python-${TARGET_PYTHON}.tar.xz" \
        -O "Python-${TARGET_PYTHON}.tar.xz"
    ls -lh "Python-${TARGET_PYTHON}.tar.xz"

    MD5=$(md5sum "Python-${TARGET_PYTHON}.tar.xz" | awk '{print $1}')
    SHA256=$(sha256sum "Python-${TARGET_PYTHON}.tar.xz" | awk '{print $1}')

    echo "PY_TARBALL_MD5=$MD5" >> "$GITHUB_ENV"
    echo "PY_TARBALL_SHA256=$SHA256" >> "$GITHUB_ENV"

    echo "======== Python ${TARGET_PYTHON} 校验和 ========"
    echo "MD5    = $MD5"
    echo "SHA256 = $SHA256"
    exit 0
fi

echo "未知子命令: $CMD"
exit 1
