import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts
import DualTone 1.0

ApplicationWindow {
    id: root
    title: "DualTone"
    visible: true
    width: 440; height: 760
    minimumWidth: 420; minimumHeight: 760
    property bool details: false
    property bool latency: false
    property bool trayAvailable: false
    readonly property color accent: "#237f6f"
    readonly property bool dark: Application.styleHints.colorScheme === Qt.Dark
    readonly property color muted: dark ? "#acb9c3" : "#667581"
    readonly property color surface: dark ? "#242c32" : "#ffffff"
    readonly property color line: dark ? "#3b454d" : "#dfe5e9"
    readonly property int routeIconSize: 20
    readonly property int routeIconGap: 12
    readonly property int routePadding: 12
    readonly property int deviceMenuPadding: 4
    readonly property int deviceItemPadding: 8
    readonly property int deviceControlHeight: 36
    readonly property int deviceItemHeight: 56
    readonly property color selectionFill: dark ? "#29453f" : "#e8f3ef"
    readonly property color hoverFill: dark ? "#333e46" : "#f0f3f5"
    font.family: "Microsoft YaHei UI"; font.pixelSize: 12
    palette.accent: accent; palette.highlight: accent
    color: dark ? "#1c2329" : "#f1f4f6"
    function deviceIndex(rows,value) {
        for (let i=0;i<rows.length;i++) if (rows[i].id===value) return i
        return 0
    }
    function analysisVisibility() { panel.setVisible(root.visible || editor.visible) }
    function openEditor() { root.details=true; editor.show(); editor.raise(); editor.requestActivate() }
    onDetailsChanged: { if (details) editor.show(); else editor.hide() }
    onVisibleChanged: analysisVisibility()
    onClosing: { editor.close(); panel.setVisible(false) }
    Component.onCompleted: analysisVisibility()
    component Subtle: Label { color: root.muted; font.pixelSize: 11 }
    component Rule: Rectangle { Layout.fillWidth: true; height: 1; color: root.line }
    component Route: ColumnLayout {
        id: route
        property string caption
        property var rows
        property string setting
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: root.routePadding+root.routeIconSize+root.routeIconGap
            Layout.rightMargin: root.routePadding
            Subtle { text: route.caption; Layout.fillWidth: true }
            Basic.Button {
                text: route.setting==="source_id" ? "交换" : "刷新"
                flat: true; implicitHeight: 20; implicitWidth: 32; padding: 0
                font.pixelSize: 11
                enabled: route.setting!=="source_id" || (!panel.telemetry.active && panel.settings.source_id.length>0 && panel.settings.target_id.length>0)
                onClicked: route.setting==="source_id" ? panel.swapRoutes() : panel.refreshDevices()
                ToolTip.visible: hovered
                ToolTip.text: route.setting==="source_id" ? "交换主副设备，同时切换 Windows 默认输出" : "重新读取当前设备"
            }
        }
        Basic.ComboBox {
            id: combo
            objectName: route.setting==="source_id" ? "sourceCombo" : "targetCombo"
            Layout.fillWidth: true; implicitHeight: root.deviceControlHeight
            leftPadding: root.routePadding; rightPadding: root.routePadding+16+root.routeIconGap
            topPadding: 8; bottomPadding: 8
            model: route.rows; textRole: "name"; valueRole: "id"
            currentIndex: root.deviceIndex(route.rows,panel.settings[route.setting])
            enabled: route.setting==="target_id" || !panel.telemetry.active
            onActivated: panel.edit(route.setting,currentValue)
            contentItem: RowLayout {
                spacing: root.routeIconGap
                Icon {
                    name: route.rows[root.deviceIndex(route.rows,panel.settings[route.setting])].icon
                    ink: root.muted
                    Layout.preferredWidth: root.routeIconSize; Layout.preferredHeight: root.routeIconSize
                    Layout.alignment: Qt.AlignVCenter
                }
                Label {
                    text: combo.currentText; elide: Text.ElideRight
                    Layout.fillWidth: true; verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 13; font.weight: Font.DemiBold
                }
            }
            background: Rectangle {
                color: combo.hovered && combo.enabled ? root.hoverFill : "transparent"
                radius: 6; border.width: combo.activeFocus ? 1 : 0; border.color: root.accent
            }
            indicator: Icon {
                name: "down"; ink: root.muted; width: 16; height: 16
                x: combo.width-root.routePadding-width; y: (combo.height-height)/2
                opacity: combo.enabled ? 1 : 0.3
            }
            delegate: Basic.ItemDelegate {
                id: option
                required property var modelData
                required property int index
                readonly property bool selected: combo.currentIndex===index && modelData.id.length>0
                width: combo.popup.availableWidth
                height: modelData.id ? root.deviceItemHeight : 40
                leftPadding: root.deviceItemPadding; rightPadding: root.deviceItemPadding
                topPadding: root.deviceItemPadding; bottomPadding: root.deviceItemPadding
                highlighted: combo.highlightedIndex===index
                enabled: modelData.supported
                contentItem: RowLayout {
                    spacing: root.routeIconGap
                    Icon {
                        name: modelData.icon; ink: root.muted
                        Layout.preferredWidth: root.routeIconSize; Layout.preferredHeight: root.routeIconSize
                        Layout.alignment: Qt.AlignVCenter
                    }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 2
                        Label {
                            text: modelData.name; elide: Text.ElideRight; Layout.fillWidth: true
                            color: root.palette.text; font.pixelSize: 12
                            font.weight: option.selected ? Font.DemiBold : Font.Normal
                        }
                        Label {
                            visible: modelData.id.length>0; text: modelData.reason || modelData.format
                            elide: Text.ElideRight; Layout.fillWidth: true
                            color: root.muted; font.pixelSize: 11
                        }
                    }
                    Icon {
                        name: "check"; ink: root.dark ? "#8bd5c4" : root.accent
                        opacity: option.selected ? 1 : 0
                        Layout.preferredWidth: 16; Layout.preferredHeight: 16
                    }
                }
                background: Rectangle {
                    radius: 4
                    color: option.selected ? root.selectionFill : ((option.highlighted || option.hovered) && option.enabled ? root.hoverFill : "transparent")
                }
            }
            popup: Basic.Popup {
                x: 0; y: combo.height+root.deviceMenuPadding
                width: combo.width; padding: root.deviceMenuPadding
                background: Rectangle { color: root.surface; border.color: root.line; radius: 8 }
                contentItem: ListView {
                    implicitHeight: Math.min(contentHeight,root.deviceItemHeight*6+40); clip: true
                    model: combo.popup.visible ? combo.delegateModel : null
                    currentIndex: combo.highlightedIndex
                    Basic.ScrollIndicator.vertical: Basic.ScrollIndicator {}
                }
            }
            ToolTip.visible: hovered
            ToolTip.text: currentText+(route.setting==="source_id" ? "\n选择后同步 Windows 默认输出；固定输出的应用需单独切换" : "\n可以在播放中切换；新连接的蓝牙音箱请先点刷新")
            ToolTip.delay: 600
            Accessible.name: route.caption
        }
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 18; spacing: 14
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            Rectangle { width: 32; height: 32; radius: 9; color: root.accent; Icon { anchors.centerIn: parent; name: "wave"; ink: "white"; width: 23; height: 23 } }
            Label { text: "DualTone"; font.family: "Segoe UI"; font.pixelSize: 21; font.weight: Font.DemiBold; Layout.fillWidth: true }
            Subtle { text: panel.telemetry.active ? "补声中" : "已停止"; color: panel.telemetry.active ? root.accent : root.muted }
            Switch { objectName: "audioSwitch"; checked: !!panel.telemetry.active; onClicked: panel.toggle(); Accessible.name: "开始或停止补声" }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: deviceRows.implicitHeight+2*root.routePadding
            color: root.surface; radius: 10; border.color: root.line
            ColumnLayout {
                id: deviceRows
                anchors.fill: parent; anchors.margins: root.routePadding; spacing: 8
                Route { caption: "主音频"; rows: panel.sources; setting: "source_id"; Layout.fillWidth: true }
                Rule {}
                Route { caption: "副音频"; rows: panel.targets; setting: "target_id"; Layout.fillWidth: true }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            RowLayout {
                Layout.fillWidth: true
                Label { text: "副音频音量"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Label { text: Number(panel.settings.gain).toFixed(1)+" %"; font.family: "Segoe UI"; font.weight: Font.DemiBold; color: root.accent }
                Button { objectName: "muteButton"; text: panel.muted ? "恢复" : "静音对比"; flat: !panel.muted; onClicked: panel.toggleMute() }
            }
            Fader { objectName: "gainSlider"; Layout.fillWidth: true; from: panel.limits.gain[0]; to: panel.limits.gain[1]; stepSize: 0.1; value: panel.settings.gain; onMoved: panel.edit("gain",Math.round(value*10)/10); Accessible.name: "补声音量百分比" }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Subtle { text: "来源" }
                Basic.ProgressBar { Layout.fillWidth: true; value: panel.telemetry.input_peak || 0; implicitHeight: 3 }
                Subtle { text: "补声" }
                Basic.ProgressBar { Layout.fillWidth: true; value: panel.telemetry.output_peak || 0; implicitHeight: 3 }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 8
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "空间补充"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    Subtle { text: "主体保留 "+Number(panel.bodyRetention).toFixed(0)+" %" }
                }
                Fader {
                    objectName: "bodyRetention"; Layout.fillWidth: true
                    from: panel.minimumBodyRetention; to: 100; stepSize: 1
                    value: panel.bodyRetention
                    onMoved: panel.setBodyRetention(value)
                    Accessible.name: "副音箱主体保留比例；向左减少主体，向右保留更多主体"
                    ToolTip.visible: hovered; ToolTip.delay: 600
                    ToolTip.text: "主体指居中的人声和乐器；左右差异保持不变。不是人声分离。"
                }
                RowLayout {
                    Layout.fillWidth: true
                    Subtle { text: "主体更少 · 环境更突出"; Layout.fillWidth: true }
                    Subtle { text: "主体更多" }
                }
            }
            RowLayout {
                Label { text: "声音处理"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                CheckBox {
                    checked: panel.settings.eq_enabled; text: "均衡器"; onClicked: panel.edit("eq_enabled",checked)
                    ToolTip.visible: hovered; ToolTip.text: "仅控制十段增益，不影响频段过滤或系统音效"
                }
                CheckBox {
                    checked: panel.settings.band_enabled; text: "多段过滤"; onClicked: panel.edit("band_enabled",checked)
                    ToolTip.visible: hovered; ToolTip.text: panel.filterSummary+"；关闭后恢复全频段"
                }
            }
            AudioPlot {
                id: miniPlot; objectName: "audioPlot"; Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 145
                compact: true
                Component.onCompleted: attach(panel)
                MouseArea { anchors.fill: parent; onDoubleClicked: root.openEditor() }
            }
            Basic.Button {
                id: detailButton; objectName: "detailsButton"; Layout.fillWidth: true; implicitHeight: 38
                onClicked: root.openEditor()
                background: Rectangle { color: detailButton.hovered ? (root.dark ? "#304139" : "#e6efec") : root.surface; radius: 7; border.color: detailButton.activeFocus ? root.accent : root.line }
                contentItem: RowLayout {
                    spacing: 10
                    Icon { name: "sliders"; ink: root.accent; width: 18; height: 18 }
                    Label { text: "详细调节"; font.weight: Font.DemiBold; Layout.fillWidth: true; color: root.palette.text }
                    Subtle { text: "EQ · 频段 · 预设" }
                    Icon { name: "chevron"; ink: root.muted; width: 14; height: 14 }
                }
                leftPadding: 12; rightPadding: 12
            }
        }
        RowLayout {
            Layout.fillWidth: true
            ComboBox { objectName: "presetCombo"; Layout.fillWidth: true; model: panel.presets; currentIndex: panel.presets.indexOf(panel.presetName); displayText: currentIndex>=0 ? currentText : panel.presetPlaceholder; enabled: count>0; onActivated: panel.usePreset(currentText); Accessible.name: "补声预设" }
            Button { text: "预设"; flat: true; onClicked: presetMenu.popup()
                Menu { id: presetMenu
                    MenuItem { text: "新增预设…"; onTriggered: panel.savePreset() }
                    MenuItem { text: "删除预设…"; enabled: panel.canDeletePreset; onTriggered: panel.deletePreset() }
                    MenuSeparator {}
                    MenuItem { text: "导入…"; onTriggered: panel.importPreset() }
                    MenuItem { text: "导出…"; onTriggered: panel.exportPreset() }
                }
            }
        }
        Rule {}
        RowLayout {
            Layout.fillWidth: true
            Basic.Button { flat: true; text: "队列 "+Number(panel.telemetry.queue_ms || 0).toFixed(1)+" ms"; onClicked: root.latency=!root.latency; ToolTip.visible: hovered; ToolTip.text: "软件播放队列，不等于声学延迟" }
            Subtle { text: "不连续 "+(panel.telemetry.discontinuities || 0); Layout.fillWidth: true }
            Basic.Button { text: "收至托盘"; flat: true; visible: root.trayAvailable; onClicked: { root.details=false; root.hide() } }
        }
        Subtle { visible: root.latency; Layout.fillWidth: true; wrapMode: Text.Wrap; text: "处理 "+Number(panel.telemetry.dsp_ms || 0).toFixed(2)+" ms · "+(panel.telemetry.source_timestamp_valid===undefined ? "时钟未检测" : panel.telemetry.source_timestamp_valid ? "时钟正常" : "时间戳异常")+" · 声学延迟未测量" }
        Label { visible: panel.message.length>0 || panel.telemetry.state==="error"; Layout.fillWidth: true; wrapMode: Text.Wrap; text: panel.message || panel.telemetry.message || "" }
    }
    Editor {
        id: editor; objectName: "editorWindow"
        visible: false
        onClosing: root.details=false
        onVisibleChanged: root.analysisVisibility()
    }
    Shortcut { sequence: "Ctrl+Return"; onActivated: panel.toggle() }
    Shortcut { sequence: "Ctrl+S"; onActivated: panel.savePreset() }
}
