// qml/FilePickerDialog.qml
// 题库选择器（Android 使用）。
// 显示应用私有目录中已导入的题库列表，并支持从剪贴板导入新题库。
// 由 main.qml 实例化，对外暴露 parentWindowWidth / parentWindowHeight / buildTag
// 三个 property。

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
                        height: 60
                        radius: 6
                        color: fileArea.pressed ? "#ecf5ff" : "transparent"
                        border.width: 1
                        border.color: fileArea.pressed ? "#409eff" : "#f0f2f5"

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            anchors.right: parent.right
                            anchors.rightMargin: 14
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

                        MouseArea {
                            id: fileArea
                            anchors.fill: parent
                            onClicked: {
                                root.close()
                                bridge.loadJsonFile(modelData.path)
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
}
