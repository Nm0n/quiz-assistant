// qml/FilePickerDialog.qml
// 题库选择器（Android 使用）。
// 显示应用私有目录中已导入的题库列表，支持导入、重命名、删除、加载。

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: root

    // ---------- 外部传入 ----------
    property real parentWindowWidth: 0
    property real parentWindowHeight: 0
    property string buildTag: ""

    title: "选择题库"
    modal: true
    anchors.centerIn: parent
    width: Math.min(parentWindowWidth - 32, 420)
    height: Math.min(parentWindowHeight - 80, 600)
    padding: 0

    property var files: []
    property string pendingRenamePath: ""
    property string pendingRenameName: ""
    property string pendingDeletePath: ""
    property string pendingDeleteName: ""

    function refresh() {
        files = bridge.listJsonFiles()
    }

    onAboutToShow: refresh()

    contentItem: Rectangle {
        implicitWidth: 380
        implicitHeight: 520
        color: "#ffffff"

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ---- 顶部：标题 + 按钮 ----
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 60
                color: "#f5f7fa"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 6

                    Text {
                        Layout.fillWidth: true
                        text: "已导入的题库"
                        font.pixelSize: 14
                        font.bold: true
                        color: "#303133"
                        verticalAlignment: Text.AlignVCenter
                    }

                    Button {
                        text: "📋 导入新题库"
                        implicitHeight: 30
                        font.pixelSize: 12
                        onClicked: {
                            bridge.importFromClipboard()
                            root.refresh()
                        }
                    }

                    Button {
                        text: "刷新"
                        implicitHeight: 30
                        implicitWidth: 60
                        font.pixelSize: 12
                        onClicked: root.refresh()
                    }
                }
            }

            // ---- 中间：列表 或 空提示 ----
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Column {
                    anchors.centerIn: parent
                    width: parent.width - 48
                    spacing: 10
                    visible: root.files.length === 0

                    Text {
                        width: parent.width
                        text: "📂"
                        font.pixelSize: 52
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Text {
                        width: parent.width
                        text: "还没有导入任何题库"
                        font.pixelSize: 15
                        font.bold: true
                        color: "#303133"
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Text {
                        width: parent.width
                        text: "点击右上角「📋 导入新题库」，从剪贴板粘贴 JSON 题库内容。"
                        wrapMode: Text.WordWrap
                        font.pixelSize: 12
                        color: "#909399"
                        horizontalAlignment: Text.AlignHCenter
                        lineHeight: 1.4
                    }
                }

                ListView {
                    anchors.fill: parent
                    anchors.margins: 8
                    clip: true
                    spacing: 2
                    visible: root.files.length > 0
                    model: root.files

                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 64
                        radius: 6
                        color: fileArea.pressed ? "#ecf5ff" : "transparent"
                        border.width: 1
                        border.color: fileArea.pressed ? "#409eff" : "#f0f2f5"

                        // MouseArea 放在底层，让上层的按钮优先接收点击
                        MouseArea {
                            id: fileArea
                            anchors.fill: parent
                            onClicked: {
                                root.close()
                                bridge.loadJsonFile(modelData.path)
                            }
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 6
                            spacing: 4

                            Column {
                                Layout.fillWidth: true
                                spacing: 3

                                Text {
                                    width: parent.width
                                    text: modelData.name
                                    font.pixelSize: 14
                                    color: "#303133"
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: (modelData.size / 1024).toFixed(1) + " KB"
                                    font.pixelSize: 11
                                    color: "#909399"
                                }
                            }

                            Button {
                                text: "改名"
                                implicitWidth: 52
                                implicitHeight: 30
                                font.pixelSize: 11
                                onClicked: {
                                    root.pendingRenamePath = modelData.path
                                    root.pendingRenameName = modelData.name
                                    renameField.text = modelData.name
                                    renameDialog.open()
                                }
                            }

                            Button {
                                text: "删除"
                                implicitWidth: 52
                                implicitHeight: 30
                                font.pixelSize: 11
                                onClicked: {
                                    root.pendingDeletePath = modelData.path
                                    root.pendingDeleteName = modelData.name
                                    deleteDialog.open()
                                }
                            }
                        }
                    }
                }
            }

            // ---- 底部：关闭 ----
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 56
                color: "#ffffff"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "关闭"
                        implicitHeight: 36
                        implicitWidth: 88
                        font.pixelSize: 13
                        onClicked: root.close()
                    }
                }
            }
        }
    }

    // ---- 重命名对话框 ----
    Dialog {
        id: renameDialog
        title: "重命名题库"
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.parentWindowWidth - 60, 340)
        standardButtons: Dialog.Ok | Dialog.Cancel

        onAccepted: {
            if (bridge.renameJsonFile(root.pendingRenamePath, renameField.text)) {
                root.refresh()
            }
        }

        contentItem: TextField {
            id: renameField
            placeholderText: "输入新的文件名（可省略 .json）"
            font.pixelSize: 14
            selectByMouse: true
        }
    }

    // ---- 删除确认对话框 ----
    Dialog {
        id: deleteDialog
        title: "删除题库"
        modal: true
        anchors.centerIn: parent
        width: Math.min(root.parentWindowWidth - 60, 340)
        standardButtons: Dialog.Ok | Dialog.Cancel

        onAccepted: {
            if (bridge.deleteJsonFile(root.pendingDeletePath)) {
                root.refresh()
            }
        }

        contentItem: Text {
            text: "确定要删除「" + root.pendingDeleteName + "」吗？\n\n此操作不可撤销。"
            wrapMode: Text.WordWrap
            font.pixelSize: 14
            color: "#303133"
        }
    }
}
