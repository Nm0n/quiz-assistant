// qml/PermissionDialog.qml
// 存储权限引导对话框。完全自包含，仅依赖外部传入的 parentWindowWidth
// 用于替代原本对 appWindow.width 的跨文件引用。

import QtQuick
import QtQuick.Controls

Dialog {
    id: root

    // ---------- 外部传入（替代 appWindow.xxx） ----------
    property real parentWindowWidth: 0

    title: "需要文件访问权限"
    modal: true
    anchors.centerIn: parent
    width: Math.min(parentWindowWidth - 40, 360)
    standardButtons: Dialog.Ok | Dialog.Cancel
    onAccepted: bridge.openStoragePermissionSettings()
    onRejected: close()

    contentItem: Text {
        text: "本应用需要「所有文件访问」权限，才能读取你放在「下载/quizassistant」目录里的题库文件。\n\n" +
              "点击「确定」将打开系统设置页面。荣耀手机上的路径通常是：\n" +
              "设置 → 应用 → 应用管理 → 智能刷题助手 → 权限 → 所有文件访问\n\n" +
              "若找不到入口，可以尝试：\n" +
              "设置 → 应用 → 权限管理 → 右上角三点 → 特殊访问权限 → 所有文件访问权限\n\n" +
              "开启后回到应用，再次点击「打开题库」即可。"
        wrapMode: Text.WordWrap
        font.pixelSize: 13
        color: "#303133"
    }
}
