// qml/QuestionPanel.qml
// 题目面板：题干 + 选项列表 + 解析
// 对外接口：question（dict）/ memoryEnabled（bool）/ getSelectedLetters()
// 对外信号：answerSelected(letter)  explanationEdited(text)

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    // ---------- 输入属性 ----------
    property var question: null
    property bool memoryEnabled: false

    // ---------- 内部状态 ----------
    // 多选进行中的本地勾选（仅未作答时使用），字母升序拼接
    property string localSelection: ""
    // 用于识别题目是否真的发生了变化
    property string currentQuestionId: ""

    // ---------- 对外信号 ----------
    signal answerSelected(string letter)
    signal explanationEdited(string text)

    // ============================================================
    // 对外方法
    // ============================================================
    function getSelectedLetters() {
        return root.localSelection
    }

    // 单选/判断题：锁定态取 userAnswer，否则为未选中
    function isLocked() {
        if (!question) return true
        return question.isAnswered || memoryEnabled
    }

    // ============================================================
    // 题目变化处理：切换题目时清空本地勾选
    // ============================================================
    onQuestionChanged: {
        if (!question) {
            currentQuestionId = ""
            localSelection = ""
            return
        }
        if (question.id !== currentQuestionId) {
            currentQuestionId = question.id
            localSelection = ""
        }
        if (question.isAnswered) {
            localSelection = ""
        }
    }

    // ============================================================
    // 布局
    // ============================================================
    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // -------- 题干卡片 --------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.max(80, stemText.implicitHeight + 30)
            color: "#ffffff"
            radius: 8
            border.width: 1
            border.color: "#dcdfe6"

            Text {
                id: stemText
                anchors.fill: parent
                anchors.margins: 15
                text: root.question ? root.question.stem
                                    : "请打开题库文件或导入 Excel 开始刷题"
                wrapMode: Text.WordWrap
                font.pixelSize: 15
                color: "#303133"
                verticalAlignment: Text.AlignVCenter
            }
        }

        // -------- 选项列表（可滚动） --------
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 120
            clip: true
            contentWidth: width
            contentHeight: optionsColumn.height
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: optionsColumn
                width: parent.width
                spacing: 8

                Repeater {
                    id: optionsRepeater
                    model: root.question ? root.question.options : []

                    delegate: OptionItem {
                        id: optionDelegate
                        width: optionsColumn.width

                        readonly property string optLetter: String.fromCharCode(65 + index)

                        letter: optLetter
                        optionText: modelData
                        multi: root.question && root.question.type === "多选题"

                        selected: {
                            if (!root.question) return false
                            if (root.question.isAnswered) {
                                return ("" + (root.question.userAnswer || "")).indexOf(optLetter) >= 0
                            }
                            return root.localSelection.indexOf(optLetter) >= 0
                        }

                        interactive: root.question
                                     && !root.question.isAnswered
                                     && !root.memoryEnabled

                        highlight: {
                            if (!root.question) return ""
                            var locked = root.question.isAnswered || root.memoryEnabled
                            if (!locked) return ""
                            var ans = "" + (root.question.answer || "")
                            var userAns = "" + (root.question.userAnswer || "")
                            if (ans.indexOf(optLetter) >= 0) return "correct"
                            if (userAns.indexOf(optLetter) >= 0) return "wrong"
                            return ""
                        }

                        onClicked: {
                            if (!root.question) return
                            if (root.question.type === "多选题") {
                                var sel = root.localSelection
                                if (sel.indexOf(optLetter) >= 0) {
                                    root.localSelection = sel.split("").filter(function(c) {
                                        return c !== optLetter
                                    }).join("")
                                } else {
                                    root.localSelection = (sel + optLetter)
                                        .split("").sort().join("")
                                }
                            } else {
                                // 单选 / 判断：立即提交
                                root.answerSelected(optLetter)
                            }
                        }
                    }
                }
            }
        }

        // -------- 解析区域（已作答或记忆模式时显示） --------
        Rectangle {
            id: explanationBox
            Layout.fillWidth: true
            visible: root.memoryEnabled || (root.question && root.question.isAnswered)
            implicitHeight: visible ? (explanationLayout.implicitHeight + 26) : 0
            color: "#fafbfc"
            radius: 8
            border.width: 1
            border.color: "#dcdfe6"

            ColumnLayout {
                id: explanationLayout
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 13
                spacing: 6

                Text {
                    text: "📝 题目解析（可编辑）"
                    font.pixelSize: 13
                    font.bold: true
                    color: "#606266"
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 90
                    clip: true

                    TextArea {
                        id: explanationArea
                        wrapMode: TextArea.Wrap
                        placeholderText: "暂无解析内容，可在此补充..."
                        font.pixelSize: 13
                        color: "#303133"
                        selectByMouse: true

                        // 防止程序化赋值触发 explanationEdited
                        property bool _syncing: false
                        property string _lastId: ""

                        function syncFromQuestion() {
                            if (!root.question) {
                                _syncing = true
                                text = ""
                                _syncing = false
                                _lastId = ""
                                return
                            }
                            if (root.question.id !== _lastId) {
                                _lastId = root.question.id
                                _syncing = true
                                text = root.question.explanation || ""
                                _syncing = false
                            }
                        }

                        onTextChanged: {
                            if (_syncing) return
                            if (!root.question) return
                            root.explanationEdited(text)
                        }

                        Component.onCompleted: syncFromQuestion()
                    }
                }
            }
        }
    }

    // ============================================================
    // 监听题目变化，驱动解析框刷新
    // ============================================================
    onCurrentQuestionIdChanged: {
        // 由 onQuestionChanged 更新 currentQuestionId 后触发
        explanationArea.syncFromQuestion()
    }

    // 已作答状态变化时也要刷新解析框（首次作答后需要回显）
    Connections {
        target: root
        function onQuestionChanged() {
            explanationArea.syncFromQuestion()
        }
    }
}