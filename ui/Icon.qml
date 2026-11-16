import QtQuick
Canvas {
    id: icon
    property string name: "speaker"
    property color ink: "#52616d"
    implicitWidth: 24
    implicitHeight: 24
    onNameChanged: requestPaint()
    onInkChanged: requestPaint()
    onPaint: {
        let c=getContext("2d");c.reset();c.scale(width/24,height/24)
        c.strokeStyle=ink;c.lineWidth=1.6;c.lineCap="round";c.lineJoin="round"
        c.beginPath()
        if (name==="speaker") {
            c.moveTo(4,9);c.lineTo(8,9);c.lineTo(13,5);c.lineTo(13,19);c.lineTo(8,15);c.lineTo(4,15);c.closePath()
            c.moveTo(17,8);c.quadraticCurveTo(21,12,17,16)
        } else if (name==="monitor") {
            c.roundedRect(3,4,18,13,2,2);c.moveTo(12,17);c.lineTo(12,21);c.moveTo(8,21);c.lineTo(16,21)
        } else if (name==="headphones") {
            c.moveTo(4,14);c.lineTo(4,10);c.bezierCurveTo(4,0,20,0,20,10);c.lineTo(20,14)
            c.roundedRect(3,12,4,8,2,2);c.roundedRect(17,12,4,8,2,2)
        } else if (name==="line") {
            c.moveTo(9,3);c.lineTo(9,7);c.moveTo(15,3);c.lineTo(15,7)
            c.roundedRect(7,7,10,8,2,2);c.moveTo(12,15);c.lineTo(12,21)
        } else if (name==="digital") {
            c.roundedRect(3,6,18,12,3,3);c.moveTo(7,10);c.lineTo(17,10);c.moveTo(7,14);c.lineTo(12,14)
        } else if (name==="sliders") {
            c.moveTo(5,3);c.lineTo(5,8);c.moveTo(5,12);c.lineTo(5,21)
            c.moveTo(12,3);c.lineTo(12,14);c.moveTo(12,18);c.lineTo(12,21)
            c.moveTo(19,3);c.lineTo(19,6);c.moveTo(19,10);c.lineTo(19,21)
            c.roundedRect(2,8,6,4,1,1);c.roundedRect(9,14,6,4,1,1);c.roundedRect(16,6,6,4,1,1)
        } else if (name==="check") { c.moveTo(5,12);c.lineTo(10,17);c.lineTo(19,7) }
        else if (name==="chevron") { c.moveTo(9,6);c.lineTo(15,12);c.lineTo(9,18) }
        else if (name==="down") { c.moveTo(6,9);c.lineTo(12,15);c.lineTo(18,9) }
        else if (name==="power") { c.arc(12,13,8,-Math.PI*.3,Math.PI*1.3);c.moveTo(12,2);c.lineTo(12,12) }
        else if (name==="wave") {
            c.moveTo(4,10);c.lineTo(4,14);c.moveTo(9,4);c.lineTo(9,20);c.moveTo(15,7);c.lineTo(15,17);c.moveTo(20,10);c.lineTo(20,14)
        } else if (name==="more") {
            c.moveTo(5,12);c.arc(5,12,1,0,2*Math.PI);c.moveTo(12,12);c.arc(12,12,1,0,2*Math.PI);c.moveTo(19,12);c.arc(19,12,1,0,2*Math.PI)
        }
        c.stroke()
    }
}
