// qml/OptionItem.qml
// 单个选项控件：支持单选/多选外观、已选回显、正确答案高亮、错误高亮
// 纯视觉组件，不直接修改业务状态，通过 clicked() 信号把交互意图交给上层

import QtQuick

Rectangle {
    id: optionRoot

    property string letter: ""       // 选项字母 A/B/C...
    property string optionText: ""   // 选项文本
    property bool multi: false       // true → 多选（方框），false → 单选（圆点）
    property bool selected: false    // 当前是否处于选中状态
    property bool interactive: true  // 是否允许点击
    property string highlight: ""    // "" | "correct" | "wrong"

    signal clicked()

    readonly property bool isCorrectHighlight: highlight === "correct"
    readonly property bool isWrongHighlight: highlight === "wrong"

    implicitHeight: Math.max(46, contentText.implicitHeight + 22)
    radius: 6
    border.width: 1

    color: isCorrectHighlight ? "#b7e4c7"
         : isWrongHighlight   ? "#f8d7da"
         : selected           ? "#ecf5ff"
         :                      "#ffffff"

    border.color: isCorrectHighlight ? "#67c23a"
                : isWrongHighlight   ? "#f56c6c"
                : selected           ? "#409eff"
                :                      "#dcdfe6"

    Row {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 10

        Rectangle {
            id: indicator
            width: 20
            height: 20
            radius: optionRoot.multi ? 4 : 10
            anchors.verticalCenter: parent.verticalCenter
            border.width: 1
            border.color: optionRoot.selected ? "#409eff" : "#c0c4cc"
            color: optionRoot.selected ? "#409eff" : "#ffffff"

            Text {
                anchors.centerIn: parent
                visible: optionRoot.selected
                text: optionRoot.multi ? "✓" : "●"
                color: "#ffffff"
                font.pixelSize: optionRoot.multi ? 13 : 9
            }
        }

        Text {
            id: contentText
            width: optionRoot.width - indicator.width - 34
            anchors.verticalCenter: parent.verticalCenter
            text: optionRoot.letter + ". " + optionRoot.optionText
            wrapMode: Text.WordWrap
            font.pixelSize: 14
            color: optionRoot.interactive ? "#303133" : "#909399"
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: optionRoot.interactive
        onClicked: optionRoot.clicked()
    }
}