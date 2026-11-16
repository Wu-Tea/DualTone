import QtQuick
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts
import DualTone 1.0

Basic.ApplicationWindow {
    id: editor
    title: "DualTone · 声音调节"
    width: 940; height: 690
    minimumWidth: 820; minimumHeight: 650
    color: "#20272d"
    font.family: "Microsoft YaHei UI"; font.pixelSize: 12
    readonly property color textColor: "#e8eef2"
    readonly property color secondary: "#a4b4c0"
    readonly property color rule: "#39434b"
    readonly property color gold: "#efc16c"
    readonly property color cyan: "#6bcfc0"
    readonly property int eqFieldMaxWidth: 72
    readonly property int eqFieldGap: 8
    readonly property int rangeRowHeight: 44
    readonly property int visibleRangeRows: height>=690 ? 3 : 2
    palette.window: color; palette.windowText: textColor; palette.text: textColor
    palette.base: "#161d22"; palette.button: "#2b343c"; palette.buttonText: textColor
    palette.mid: rule; palette.dark: rule; palette.light: "#46545f"
    palette.highlight: "#448c7d"; palette.highlightedText: "#ffffff"
    palette.accent: cyan; palette.placeholderText: secondary
    component Caption: Basic.Label { color: editor.secondary; font.pixelSize: 11 }
    component NumberField: Basic.TextField {
        id: field
        property real number: 0
        property real lower: 0
        property real upper: 16000
        property int decimals: 0
        property string unit: "Hz"
        property bool edited: false
        property string validationMessage: ""
        readonly property string rangeText: Number(lower).toFixed(decimals)+"–"+Number(upper).toFixed(decimals)+" "+unit
        signal submitted(real value)
        text: Number(number).toFixed(decimals)
        implicitWidth: 78; implicitHeight: 30
        color: editor.textColor; horizontalAlignment: Text.AlignHCenter; selectByMouse: true
        validator: DoubleValidator { bottom: field.lower; top: field.upper; decimals: field.decimals; locale: "en_US" }
        function finishEdit() {
            if (!edited) return
            edited=false
            if (acceptableInput) {
                submitted(Number(text))
                validationMessage=""
            } else {
                validationMessage="未应用：请输入 "+rangeText+"；已恢复 "+Number(number).toFixed(decimals)+" "+unit
            }
            // Restore the binding, not just the text, so later preset/CLI edits
            // remain visible after rejecting an incomplete or invalid entry.
            text=Qt.binding(function() { return Number(field.number).toFixed(field.decimals) })
        }
        onTextEdited: {
            edited=true
            validationMessage=acceptableInput ? "" : "请输入 "+rangeText+"；当前生效 "+Number(number).toFixed(decimals)+" "+unit
        }
        onEditingFinished: finishEdit()
        onActiveFocusChanged: { if (!activeFocus) finishEdit(); else validationMessage="" }
        Keys.onReturnPressed: finishEdit()
        Keys.onEnterPressed: finishEdit()
        Keys.onEscapePressed: {
            edited=false;validationMessage=""
            text=Qt.binding(function() { return Number(field.number).toFixed(field.decimals) })
        }
        Basic.ToolTip.visible: validationMessage.length>0
        Basic.ToolTip.text: validationMessage
        Basic.ToolTip.delay: 400
        Basic.ToolTip.timeout: 3500
        background: Rectangle { color: "#161d22"; radius: 4; border.color: field.edited && !field.acceptableInput ? "#e59b87" : field.activeFocus ? editor.cyan : editor.rule }
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 0
        RowLayout {
            Layout.fillWidth: true; Layout.margins: 18; spacing: 14
            Icon { name: "sliders"; ink: editor.cyan; width: 22; height: 22 }
            Basic.Label { text: "声音调节"; font.pixelSize: 17; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            Basic.ComboBox {
                Layout.preferredWidth: 210; model: panel.presets
                currentIndex: panel.presets.indexOf(panel.presetName)
                displayText: currentIndex>=0 ? currentText : panel.presetPlaceholder
                enabled: count>0
                onActivated: panel.usePreset(currentText)
                Accessible.name: "补声预设"
            }
            Basic.Button { text: "新增预设"; onClicked: panel.savePreset() }
            Basic.Button {
                text: "删除预设"; enabled: panel.canDeletePreset; onClicked: panel.deletePreset()
                Basic.ToolTip.visible: hovered
                Basic.ToolTip.text: panel.canDeletePreset ? "删除所选自定义预设，保留当前声音设置" : "选择已保存的预设后可删除"
            }
            Basic.Button { text: "更多"; onClicked: presetFiles.popup()
                Basic.Menu { id: presetFiles
                    Basic.MenuItem { text: "导入配置…"; onTriggered: panel.importPreset() }
                    Basic.MenuItem { text: "导出配置…"; onTriggered: panel.exportPreset() }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: editor.rule }
        RowLayout {
            Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.topMargin: 10; Layout.bottomMargin: 4; spacing: 14
            Rectangle { width: 15; height: 2; color: editor.gold }
            Caption { text: "均衡曲线" }
            Rectangle { width: 15; height: 2; color: "#a5a481"; visible: panel.settings.band_enabled }
            Caption { text: "过滤后"; visible: panel.settings.band_enabled }
            Rectangle { width: 15; height: 2; color: "#8d9da9" }
            Caption { text: "来源频谱" }
            Rectangle { width: 15; height: 2; color: editor.cyan }
            Caption { text: "补声频谱" }
            Item { Layout.fillWidth: true }
            Basic.Button { text: "本机音效…"; flat: true; onClicked: panel.showSystemEffects() }
        }
        AudioPlot {
            id: graph; objectName: "detailPlot"
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 230
            Component.onCompleted: attach(panel)
            Accessible.name: "处理曲线；拖动频点调节 EQ"
            MouseArea {
                anchors.fill: parent
                onPressed: function(mouse) { forceActiveFocus();graph.selectAt(mouse.x,mouse.y) }
                onDoubleClicked: { graph.resetSelected() }
                Keys.onLeftPressed: graph.stepSelected(-1)
                Keys.onRightPressed: graph.stepSelected(1)
                Keys.onUpPressed: graph.adjustSelected(0.5)
                Keys.onDownPressed: graph.adjustSelected(-0.5)
                Basic.ToolTip.visible: containsMouse && !pressed
                Basic.ToolTip.delay: 900
                Basic.ToolTip.text: "拖动频点调节增益；双击归零；方向键微调"
                hoverEnabled: true
                onPositionChanged: function(mouse) { if (pressed) graph.dragTo(mouse.y) }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.topMargin: 6; Layout.bottomMargin: 10
            Basic.CheckBox {
                text: "十段均衡器"; checked: panel.settings.eq_enabled; onClicked: panel.edit("eq_enabled",checked)
                Basic.ToolTip.visible: hovered
                Basic.ToolTip.text: "只控制下方十段增益；关闭时保留数值，不影响频段过滤或系统音效"
            }
            Caption { text: graph.selectedBand>=0 ? panel.frequencies[graph.selectedBand]+" Hz   "+Number(panel.settings.gains[graph.selectedBand]).toFixed(1)+" dB" : ""; Layout.fillWidth: true }
            Basic.Button { text: "增益归零"; flat: true; onClicked: panel.flat() }
            Caption { text: "余量 "+Number(-panel.headroom).toFixed(1)+" dB" }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: editor.rule }
        Item {
            Layout.fillWidth: true; Layout.preferredHeight: 76
            readonly property real fieldWidth: Math.min(editor.eqFieldMaxWidth,graph.width>0 ? graph.minimumBandSpacing()-editor.eqFieldGap : editor.eqFieldMaxWidth)
            Repeater {
                model: panel.frequencies
                ColumnLayout {
                    id: band
                    required property int index
                    required property var modelData
                    x: (graph.width>0 ? graph.bandPosition(modelData) : 0)-width/2
                    y: 10; width: parent.fieldWidth; spacing: 8
                    enabled: panel.settings.eq_enabled
                    opacity: enabled ? 1 : 0.4
                    Caption { Layout.alignment: Qt.AlignHCenter; text: band.modelData>=1000 ? band.modelData/1000+"k" : band.modelData; color: graph.selectedBand===band.index ? editor.gold : editor.secondary }
                    Basic.TextField {
                        id: eqValue
                        objectName: "bandValue"+band.index
                        Layout.fillWidth: true; implicitHeight: 30
                        horizontalAlignment: Text.AlignHCenter; selectByMouse: true
                        text: Number(panel.settings.gains[band.index]).toFixed(1)
                        color: editor.textColor
                        validator: DoubleValidator { bottom: -panel.limits.eq; top: panel.limits.eq; decimals: 1; locale: "en_US" }
                        onEditingFinished: if (acceptableInput) panel.setBand(band.index,Number(text))
                        background: Rectangle { color: "#161d22"; radius: 4; border.color: eqValue.activeFocus ? editor.gold : editor.rule }
                        Accessible.name: band.modelData+" Hz 分贝数值"
                    }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: editor.rule }
        RowLayout {
            Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22
            Layout.topMargin: 6; Layout.bottomMargin: 4; spacing: 12
            Basic.CheckBox {
                text: "多段过滤"; checked: panel.settings.band_enabled; onClicked: panel.edit("band_enabled",checked)
                Basic.ToolTip.visible: hovered
                Basic.ToolTip.text: "混合所有启用的频段；关闭后恢复全频段。各段增益为相对权重，总输出保留防削波余量。"
            }
            Caption { text: panel.settings.band_enabled ? panel.filterBands.filter(function(b) { return b.enabled }).length+" 段启用" : "已旁通" }
            Basic.Button { objectName: "addFilterBand"; text: "新增频段"; flat: true; enabled: panel.filterBands.length<panel.limits.max_bands; onClicked: panel.addFilterBand() }
            Item { Layout.fillWidth: true }
            Caption { text: "副音频 "+Number(panel.settings.gain).toFixed(1)+" %" }
            Basic.Button { text: panel.muted ? "恢复补声" : "静音对比"; highlighted: panel.muted; onClicked: panel.toggleMute() }
        }
        Basic.ScrollView {
            Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.bottomMargin: 14
            Layout.preferredHeight: Math.min(filterRows.implicitHeight,editor.rangeRowHeight*editor.visibleRangeRows)
            contentWidth: availableWidth; clip: true
            Basic.ScrollBar.horizontal.policy: Basic.ScrollBar.AlwaysOff
            Basic.ScrollBar.vertical.policy: contentHeight>availableHeight ? Basic.ScrollBar.AlwaysOn : Basic.ScrollBar.AlwaysOff
            ColumnLayout {
                id: filterRows; width: parent.width; spacing: 4
                Repeater {
                    model: panel.filterBands.length
                    RowLayout {
                        id: rangeRow
                        required property int index
                        readonly property var values: panel.filterBands[index] || ({low:50,high:100,gain_db:0,enabled:false})
                        Layout.fillWidth: true; spacing: 10
                        Basic.CheckBox {
                            Layout.preferredWidth: 104; text: "频段 "+(rangeRow.index+1)
                            checked: rangeRow.values.enabled
                            onClicked: panel.editFilterBand(rangeRow.index,"enabled",checked)
                            Accessible.name: "启用频段 "+(rangeRow.index+1)
                        }
                        Caption { text: "下限" }
                        NumberField {
                            objectName: rangeRow.index===0 ? "lowFrequency" : "lowFrequency"+rangeRow.index
                            Layout.preferredWidth: 78; number: rangeRow.values.low
                            lower: panel.limits.low[0]; upper: Math.min(panel.limits.low[1],rangeRow.values.high-1)
                            onSubmitted: function(v) { panel.editFilterBand(rangeRow.index,"low",v) }
                            Accessible.name: "频段 "+(rangeRow.index+1)+" 下限 Hz"
                        }
                        Caption { text: "上限" }
                        NumberField {
                            objectName: rangeRow.index===0 ? "highFrequency" : "highFrequency"+rangeRow.index
                            Layout.preferredWidth: 78; number: rangeRow.values.high
                            lower: Math.max(panel.limits.high[0],rangeRow.values.low+1); upper: panel.limits.high[1]
                            onSubmitted: function(v) { panel.editFilterBand(rangeRow.index,"high",v) }
                            Accessible.name: "频段 "+(rangeRow.index+1)+" 上限 Hz"
                        }
                        Caption { text: "Hz"; Layout.rightMargin: 12 }
                        Caption { text: "增益" }
                        NumberField {
                            objectName: "rangeGain"+rangeRow.index
                            Layout.preferredWidth: 68; number: rangeRow.values.gain_db; decimals: 1; unit: "dB"
                            lower: panel.limits.band_gain_db[0]; upper: panel.limits.band_gain_db[1]
                            onSubmitted: function(v) { panel.editFilterBand(rangeRow.index,"gain_db",v) }
                            Accessible.name: "频段 "+(rangeRow.index+1)+" 增益 dB"
                        }
                        Caption { text: "dB" }
                        Item { Layout.fillWidth: true }
                        Basic.Button {
                            text: "删除"; flat: true; enabled: panel.filterBands.length>1
                            onClicked: panel.deleteFilterBand(rangeRow.index)
                            Accessible.name: "删除频段 "+(rangeRow.index+1)
                        }
                    }
                }
            }
        }
    }
}
