// qml/main.qml
// 主窗口：布局、顶部状态区、进度条、题目区域、底部按钮区、抽屉菜单。
// 所有业务调用统一走 bridge（在 main.py 中注册的 ControllerBridge）。

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: appWindow

    visible: true
    width: 420
    height: 800
    color: "#f0f2f5"

    // ============================================================
    // 视图状态（全部来自 bridge）
    // ============================================================
    readonly property var viewState: bridge.viewState

    // currentQuestion 是唯一真相来源：
    //   直接基于 viewState 判断，避免独立的 hasQuestion 绑定
    //   与 currentQuestion 绑定求值顺序不一致导致短暂 null。
    readonly property var currentQuestion: {
        var s = viewState
        if (s && s.hasQuestion && s.question && s.question.id)
            return s.question
        return null
    }
    readonly property bool hasQuestion: currentQuestion !== null

    readonly property string fileLabel:
        (viewState && viewState.fileName) ? viewState.fileName : "未命名"
    readonly property string modifiedMark:
        (viewState && viewState.isModified) ? " *" : ""
    readonly property bool memoryEnabled:
        viewState ? viewState.memoryEnabled : false
    readonly property bool shuffleEnabled:
        viewState ? viewState.shuffleEnabled : false

    // Excel 导入开关：Android 端 pandas/openpyxl 不可用，默认禁用。
    // 若未来在桌面端启用，把 false 改为 true 即可。
    readonly property bool excelImportEnabled: false

    title: "智能刷题助手 - " + fileLabel + modifiedMark

    // ============================================================
    // 内联组件
    // ============================================================

    component FlatButton: Button {
        id: control
        implicitHeight: 42
        font.pixelSize: 13

        property color fgColor: "#606266"
        property color borderColor: "#dcdfe6"
        property color bgColor: "#ffffff"

        contentItem: Text {
            text: control.text
            font: control.font
            color: control.enabled ? control.fgColor : "#c0c4cc"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        background: Rectangle {
            radius: 6
            color: !control.enabled ? "#f5f7fa"
                 : control.down ? "#d9ecff"
                 : control.bgColor
            border.width: 1
            border.color: !control.enabled ? "#e4e7ed" : control.borderColor
        }
    }

    component PrimaryButton: FlatButton {
        fgColor: "#ffffff"
        borderColor: "#409eff"
        bgColor: "#409eff"
    }

    component MenuEntry: Rectangle {
        id: entry
        property string label: ""
        signal clicked()

        height: 46
        radius: 6
        color: entryArea.pressed ? "#ecf5ff" : "transparent"

        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.right: parent.right
            anchors.rightMargin: 12
            text: entry.label
            font.pixelSize: 15
            color: "#303133"
            elide: Text.ElideRight
        }

        MouseArea {
            id: entryArea
            anchors.fill: parent
            onClicked: entry.clicked()
        }
    }

    component MenuSection: Text {
        height: 32
        leftPadding: 8
        font.pixelSize: 13
        font.bold: true
        color: "#909399"
        verticalAlignment: Text.AlignBottom
    }

    // ============================================================
    // 文件对话框
    // 【Android 兼容性修复】
    //   1) onAccepted / onRejected 里显式 close()，确保对话框真正关闭
    //   2) 每次打开前清空 selectedFile，避免上次的选择残留
    //   3) 通过 openFileDialogTimer 延迟打开，避开 Drawer 关闭动画
    // ============================================================
    FileDialog {
        id: openJsonDialog
        title: "选择题库文件"
        nameFilters: ["JSON 文件 (*.json)", "所有文件 (*)"]
        onAccepted: {
            var path = selectedFile.toString()
            console.log("[FileDialog] openJson accepted: " + path)
            close()
            selectedFile = null
            bridge.loadFromJson(path)
        }
        onRejected: {
            console.log("[FileDialog] openJson rejected")
            close()
            selectedFile = null
        }
    }

    FileDialog {
        id: saveJsonDialog
        title: "保存题库"
        fileMode: FileDialog.SaveFile
        nameFilters: ["JSON 文件 (*.json)"]
        defaultSuffix: "json"
        onAccepted: {
            var path = selectedFile.toString()
            console.log("[FileDialog] saveJson accepted: " + path)
            close()
            selectedFile = null
            bridge.saveToFile(path)
        }
        onRejected: {
            console.log("[FileDialog] saveJson rejected")
            close()
            selectedFile = null
        }
    }

    FileDialog {
        id: importExcelDialog
        title: "选择 Excel 文件（Android 端可能不可用）"
        nameFilters: ["Excel 文件 (*.xlsx *.xls)", "所有文件 (*)"]
        onAccepted: {
            var path = selectedFile.toString()
            console.log("[FileDialog] importExcel accepted: " + path)
            close()
            selectedFile = null
            bridge.loadFromExcel(path)
        }
        onRejected: {
            console.log("[FileDialog] importExcel rejected")
            close()
            selectedFile = null
        }
    }

    // ============================================================
    // 【新增】延迟打开 FileDialog 的中介 Timer
    //   原因：Drawer 关闭有 300ms 动画，与 FileDialog.open() 同时发生
    //        在 Android 上会让系统文件选择器 Activity 启动失败。
    //   做法：先关闭 Drawer，350ms 后再打开 FileDialog。
    // ============================================================
    Timer {
        id: openFileDialogTimer
        property var targetDialog: null

        interval: 350
        repeat: false

        onTriggered: {
            if (targetDialog) {
                targetDialog.selectedFile = null  // 关键：重置上次选择
                targetDialog.open()
            }
        }
    }

    // ============================================================
    // 消息对话框
    // ============================================================
    Dialog {
        id: messageDialog
        property string heading: ""
        property string body: ""

        modal: true
        anchors.centerIn: parent
        width: Math.min(appWindow.width - 60, 360)
        title: heading
        standardButtons: Dialog.Ok

        contentItem: Text {
            text: messageDialog.body
            wrapMode: Text.WordWrap
            font.pixelSize: 14
            color: "#303133"
        }
    }

    // ============================================================
    // 工具函数
    // ============================================================
    function showMessage(heading, body) {
        messageDialog.heading = heading
        messageDialog.body = body
        messageDialog.open()
    }

    function showToast(msg) {
        toast.show(msg)
    }

    function doSave() {
        if (!appWindow.hasQuestion) {
            appWindow.showToast("没有可保存的数据")
            return
        }
        var ok = bridge.saveCurrent()
        if (!ok) {
            saveJsonDialog.selectedFile = null  // 关键：重置
            saveJsonDialog.open()
        }
    }

    // ============================================================
    // bridge 信号连接
    // ============================================================
    Connections {
        target: bridge
        function onInfoMessage(msg) { appWindow.showToast(msg) }
        function onErrorOccurred(msg) { appWindow.showMessage("提示", msg) }
    }

    // ============================================================
    // 顶栏
    // ============================================================
    header: ToolBar {
        height: 52
        background: Rectangle { color: "#ffffff" }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 4
            anchors.rightMargin: 8
            spacing: 4

            ToolButton {
                text: "☰"
                font.pixelSize: 20
                onClicked: menuDrawer.open()
            }

            Label {
                Layout.fillWidth: true
                text: appWindow.fileLabel + appWindow.modifiedMark
                elide: Text.ElideRight
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 15
                font.bold: true
                color: "#303133"
            }

            ToolButton {
                text: "💾"
                font.pixelSize: 18
                enabled: appWindow.hasQuestion
                onClicked: appWindow.doSave()
            }
        }
    }

    // ============================================================
    // 抽屉菜单
    // ============================================================
    Drawer {
        id: menuDrawer
        edge: Qt.LeftEdge
        width: Math.min(appWindow.width * 0.82, 300)
        height: appWindow.height

        Column {
            id: menuColumn
            anchors.fill: parent
            anchors.margins: 14
            spacing: 2

            MenuSection { width: menuColumn.width; text: "📁 文件" }

            MenuEntry {
                width: menuColumn.width
                label: "打开题库"
                onClicked: {
                    menuDrawer.close()
                    openFileDialogTimer.targetDialog = openJsonDialog
                    openFileDialogTimer.start()
                }
            }
            MenuEntry {
                width: menuColumn.width
                label: "保存"
                onClicked: { menuDrawer.close(); appWindow.doSave() }
            }
            MenuEntry {
                width: menuColumn.width
                label: "另存为"
                onClicked: {
                    menuDrawer.close()
                    openFileDialogTimer.targetDialog = saveJsonDialog
                    openFileDialogTimer.start()
                }
            }
            MenuEntry {
                width: menuColumn.width
                label: "导入 Excel"
                visible: appWindow.excelImportEnabled
                height: appWindow.excelImportEnabled ? 46 : 0
                onClicked: {
                    menuDrawer.close()
                    openFileDialogTimer.targetDialog = importExcelDialog
                    openFileDialogTimer.start()
                }
            }

            MenuSection { width: menuColumn.width; text: "📚 刷题模式" }
            Repeater {
                model: [
                    { mode: "all",      label: "全量刷题" },
                    { mode: "wrong",    label: "错题重做" },
                    { mode: "favorite", label: "收藏复习" }
                ]
                delegate: MenuEntry {
                    width: menuColumn.width
                    label: {
                        var s = appWindow.viewState
                        var mark = (s && s.currentMode === modelData.mode) ? "✓  " : "    "
                        return mark + modelData.label
                    }
                    onClicked: {
                        menuDrawer.close()
                        bridge.switchMode(modelData.mode)
                    }
                }
            }

            MenuSection { width: menuColumn.width; text: "ℹ️ 关于" }
            MenuEntry {
                width: menuColumn.width
                label: "退出"
                onClicked: { menuDrawer.close(); Qt.quit() }
            }

            Item { width: 1; height: 12 }
            Text {
                width: menuColumn.width
                text: "提示：Android 端仅支持 JSON 题库。"
                wrapMode: Text.WordWrap
                font.pixelSize: 11
                color: "#909399"
                leftPadding: 8
                topPadding: 8
            }
        }
    }

    // ============================================================
    // 主内容
    // ============================================================
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // -------- 题号 + 收藏/错题标签 --------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Label {
                text: {
                    var s = appWindow.viewState
                    if (!appWindow.hasQuestion || !s) return "第 0 / 0 题"
                    return "第 " + s.index + " / " + s.total + " 题"
                }
                font.pixelSize: 16
                font.bold: true
                color: "#303133"
            }

            Rectangle {
                visible: tagText.text.length > 0
                Layout.preferredHeight: 24
                Layout.preferredWidth: tagText.implicitWidth + 20
                radius: 4
                color: "#ffffff"
                border.width: 1
                border.color: "#e4e7ed"

                Text {
                    id: tagText
                    anchors.centerIn: parent
                    text: {
                        var q = appWindow.currentQuestion
                        if (!q) return ""
                        var parts = []
                        if (q.isFavorite) parts.push("⭐ 收藏")
                        if (q.isWrong) parts.push("❌ 错题")
                        return parts.join("  ")
                    }
                    font.pixelSize: 12
                    font.bold: true
                    color: "#606266"
                }
            }

            Item { Layout.fillWidth: true }
        }

        // -------- 收藏 / 错题 / 记忆 按钮 --------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FlatButton {
                Layout.fillWidth: true
                text: {
                    var q = appWindow.currentQuestion
                    return (q && q.isFavorite) ? "★ 已收藏" : "☆ 收藏"
                }
                enabled: appWindow.hasQuestion
                fgColor: "#f5a623"
                borderColor: "#f5a623"
                onClicked: bridge.toggleFavorite()
            }

            FlatButton {
                Layout.fillWidth: true
                text: {
                    var q = appWindow.currentQuestion
                    return (q && q.isWrong) ? "取消错题" : "标记错题"
                }
                enabled: appWindow.hasQuestion
                fgColor: "#f56c6c"
                borderColor: "#f56c6c"
                onClicked: bridge.toggleWrong()
            }

            FlatButton {
                Layout.fillWidth: true
                text: appWindow.memoryEnabled ? "退出记忆" : "🧠 记忆"
                fgColor: appWindow.memoryEnabled ? "#ffffff" : "#606266"
                borderColor: appWindow.memoryEnabled ? "#606266" : "#909399"
                bgColor: appWindow.memoryEnabled ? "#909399" : "#ffffff"
                onClicked: bridge.toggleMemoryMode()
            }
        }

        // -------- 进度条 --------
        ProgressBar {
            id: progressBar
            Layout.fillWidth: true
            Layout.preferredHeight: 10
            from: 0
            to: 100
            value: {
                var s = appWindow.viewState
                return (appWindow.hasQuestion && s) ? s.progress : 0
            }

            background: Rectangle {
                implicitHeight: 10
                radius: 5
                color: "#e4e7ed"
            }
            contentItem: Item {
                Rectangle {
                    width: progressBar.visualPosition * parent.width
                    height: parent.height
                    radius: 5
                    color: "#67c23a"
                }
            }
        }

        // -------- 题目面板 --------
        QuestionPanel {
            id: questionPanel
            Layout.fillWidth: true
            Layout.fillHeight: true

            question: appWindow.currentQuestion
            memoryEnabled: appWindow.memoryEnabled

            onAnswerSelected: function(letter) {
                bridge.submitAnswer(letter)
            }
            onExplanationEdited: function(text) {
                bridge.updateExplanation(text)
            }
        }

        // -------- 上一题 / 下一题 --------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FlatButton {
                Layout.fillWidth: true
                text: "◀ 上一题"
                enabled: appWindow.hasQuestion
                onClicked: bridge.prevQuestion()
            }
            FlatButton {
                Layout.fillWidth: true
                text: "下一题 ▶"
                enabled: appWindow.hasQuestion
                onClicked: bridge.nextQuestion()
            }
        }

        // -------- 提交 / 乱序 / Excel --------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            PrimaryButton {
                Layout.fillWidth: true
                text: "提交答案"
                // ★ 用显式块体 + 局部变量缓存，避免多行 && 在绑定引擎中
                //   对 currentQuestion 反复求值导致的时序错位。
                enabled: {
                    var q = appWindow.currentQuestion
                    if (!q) return false
                    if (q.type !== "多选题") return false
                    if (q.isAnswered) return false
                    if (appWindow.memoryEnabled) return false
                    return true
                }
                onClicked: {
                    var ans = questionPanel.getSelectedLetters()
                    if (!ans || ans.length === 0) {
                        appWindow.showToast("请至少选择一个选项")
                        return
                    }
                    bridge.submitAnswer(ans)
                }
            }

            FlatButton {
                id: shuffleButton
                Layout.fillWidth: true
                text: appWindow.shuffleEnabled ? "🎲 乱序 ✓" : "🎲 随机顺序"
                checkable: true
                checked: appWindow.shuffleEnabled
                onClicked: {
                    var enabled = bridge.toggleShuffle()
                    checked = enabled
                }
            }

            FlatButton {
                Layout.fillWidth: true
                text: "📂 Excel"
                visible: appWindow.excelImportEnabled
                Layout.preferredWidth: appWindow.excelImportEnabled ? -1 : 0
                onClicked: {
                    importExcelDialog.selectedFile = null
                    importExcelDialog.open()
                }
            }
        }

        // -------- 状态栏 --------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 30
            radius: 6
            color: "#ffffff"
            border.width: 1
            border.color: "#e4e7ed"

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: 10
                anchors.right: parent.right
                anchors.rightMargin: 10
                elide: Text.ElideRight
                font.pixelSize: 12
                color: "#606266"
                text: {
                    var s = appWindow.viewState
                    if (!s || !appWindow.hasQuestion) return "准备就绪"
                    var t = "🏆 得分: " + s.score
                          + "   |   📖 模式: " + s.modeDisplay
                    if (s.memoryEnabled) t += "   |   🧠 记忆模式"
                    return t
                }
            }
        }
    }

    // ============================================================
    // Toast（轻提示）
    // ============================================================
    Rectangle {
        id: toast
        property string message: ""

        z: 999
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 70

        width: Math.min(appWindow.width - 60, toastText.implicitWidth + 36)
        height: toastText.implicitHeight + 22
        radius: 8
        color: "#303133"
        opacity: 0
        visible: opacity > 0

        Text {
            id: toastText
            anchors.centerIn: parent
            text: toast.message
            color: "#ffffff"
            font.pixelSize: 13
            wrapMode: Text.WordWrap
            width: toast.width - 24
            horizontalAlignment: Text.AlignHCenter
        }

        Behavior on opacity { NumberAnimation { duration: 180 } }

        Timer {
            id: toastTimer
            interval: 2200
            onTriggered: toast.opacity = 0
        }

        function show(msg) {
            message = msg
            opacity = 1
            toastTimer.restart()
        }
    }
}
