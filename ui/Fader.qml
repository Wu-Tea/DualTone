import QtQuick
import QtQuick.Controls.Basic as Basic
Basic.Slider {
    id: control
    property color tint: "#248b77"
    property color track: "#dce2e5"
    property bool bipolar: false
    implicitHeight: horizontal ? 30 : 98
    implicitWidth: horizontal ? 160 : 32
    padding: 8
    background: Rectangle {
        x: control.horizontal ? control.leftPadding : (control.width-width)/2
        y: control.horizontal ? (control.height-height)/2 : control.topPadding
        width: control.horizontal ? control.availableWidth : 3
        height: control.horizontal ? 4 : control.availableHeight
        radius: 2; color: control.track
        Rectangle {
            visible: !control.bipolar
            width: control.horizontal ? parent.width*control.position : parent.width
            height: control.horizontal ? parent.height : parent.height*control.position
            anchors.bottom: parent.bottom
            radius: 2; color: control.enabled ? control.tint : control.track
        }
    }
    handle: Rectangle {
        x: control.horizontal ? control.leftPadding+control.visualPosition*(control.availableWidth-width) : (control.width-width)/2
        y: control.horizontal ? (control.height-height)/2 : control.topPadding+control.visualPosition*(control.availableHeight-height)
        implicitWidth: 18; implicitHeight: 18; radius: 9
        color: control.pressed ? control.tint : "#ffffff"
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus || control.hovered ? control.tint : "#a4afb7"
        Rectangle { anchors.centerIn: parent; width: 6; height: 6; radius: 3; color: control.tint; visible: !control.pressed && control.enabled }
    }
}
