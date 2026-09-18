// qml/Toast.qml
// 轻提示控件。由 main.qml 以 ApplicationWindow 直接子级方式实例化，
// 因此 anchors.horizontalCenter / anchors.bottom 的 parent 与拆分前一致。
// 通过 parentWindowWidth property 替代原本对 appWindow.width 的跨文件引用。

import QtQuick

Rectangle {
    id: root

    // ---------- 外部传入（替代 appWindow.xxx） ----------
    property real parentWindowWidth: 0

    property string message: ""

    z: 999
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: 70

    width: Math.min(root.parentWindowWidth - 60, toastText.implicitWidth + 36)
    height: toastText.implicitHeight + 22
    radius: 8
    color: "#303133"
    opacity: 0
    visible: opacity > 0

    Text {
        id: toastText
        anchors.centerIn: parent
        text: root.message
        color: "#ffffff"
        font.pixelSize: 13
        wrapMode: Text.WordWrap
        width: root.width - 24
        horizontalAlignment: Text.AlignHCenter
    }

    Behavior on opacity { NumberAnimation { duration: 180 } }

    Timer {
        id: toastTimer
        interval: 2200
        onTriggered: root.opacity = 0
    }

    function show(msg) {
        message = msg
        opacity = 1
        toastTimer.restart()
    }
}
