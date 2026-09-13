; pysidedeploy.spec
; PySide6 部署配置文件（同时适用于桌面端 pyside6-deploy 与 Android 端 pyside6-android-deploy）
;
; 说明：
;   1) 不同 PySide6 小版本对 spec 字段的支持略有差异，若某字段不被识别，
;      打包工具会忽略它并给出警告，不影响打包流程。
;   2) Android 打包时，SDK / NDK 路径一般通过环境变量传入
;      （ANDROID_HOME / ANDROID_NDK_HOME），此处的值仅作为回退默认值。
;   3) 由于 core/ 严禁修改，本 spec 不做任何源码级 hook，
;      所需适配全部在 main.py 的 ControllerBridge 中完成。

[app]
; 应用显示名称（Android 桌面图标下方文字）
title = 智能刷题助手
; 内部包名（Android applicationId，需唯一）
package_name = org.quizassistant.app
; 应用短名（用于生成中间产物目录名）
name = quizassistant
; 版本号
version = 1.0.0
; Android versionCode（整数，每次发版需递增）
version_code = 1
; 入口 Python 文件（相对于 project_dir）
entry_point = main.py
; 应用图标（留空则使用默认图标；如需自定义，放到 icons/ 下并填相对路径）
icon =

[python]
; 目标 Python 版本（须与 pyside6-android-deploy 使用的 CPython 一致）
python_version = 3.11
; 额外需要打入的第三方依赖。
; 注意：pandas / numpy 在 Android 上大概率无法加载（缺少预编译 wheel），
;       因此默认不打包；Excel 导入功能请改在桌面端预处理为 JSON。
requirements =
    PySide6

[qt]
; 需要打包的 Qt 模块
modules =
    Core
    Gui
    Qml
    Quick
    QuickControls2
    Widgets

[qml]
; QML 资源目录（相对 project_dir）
; 打包时会把该目录整体复制进应用资源
qml_dir = qml
; QML 主文件（相对 qml_dir）
qml_entry = main.qml

[android]
; 目标平台
platform = android
; 打包格式：apk 或 aab
format = apk
; CPU 架构（arm64-v8a 覆盖绝大多数现代设备）
architecture = arm64-v8a
; 最低支持 Android 版本（API Level）
min_sdk = 26
; 目标 Android 版本（API Level）
target_sdk = 33
; 屏幕方向（portrait / landscape / sensor）
orientation = portrait
; SDK / NDK 路径（留空则从环境变量读取）
sdk_path =
ndk_path =
; 是否启用调试符号
debug = false

[desktop]
; 桌面端（用于本地验证）部署参数
platform = desktop
format =
    onedir