"""Qt Quick presentation and analysis. Audio forwarding never calls into Qt."""
import math
import numpy as np
from scipy.signal import sosfreqz
from PySide6.QtCore import QObject,Property,Signal,Slot,QTimer,QRectF,Qt
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QFont
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtWidgets import QFileDialog,QInputDialog,QMessageBox
from routing import sync_main_output,prepare_auxiliary_switch
from spatial import mid_gain
from config import SPATIAL_MAX_MID_CUT_DB
from system_effects import effects_report,report_text
from band_filter import band_response
from config import MAX_FILTER_BANDS,FILTER_BAND_GAIN_DB,NEW_FILTER_BAND_LOW_HZ,NEW_FILTER_BAND_HIGH_HZ
from audio_engine import Engine,devices,compile_dsp
from control import Server
from settings import Store,validate,merge_settings
from config import (EQ_FREQUENCIES_HZ,EQ_MAX_DB,PARAMETER_LIMITS,TARGET_RATE_HZ,
    SUPPORTED_SOURCE_RATES_HZ,CHANNEL_COUNT,PRESET_MAX_COUNT,
    PRESET_NAME_MAX_CHARS,EQ_HEADROOM_DB,UI_REFRESH_MS,UI_EDIT_DEBOUNCE_MS,UI_SAVE_DEBOUNCE_MS,
    SPECTRUM_FFT_FRAMES,SPECTRUM_FLOOR_DB,SPECTRUM_DISPLAY_POINTS,
    PLOT_MIN_FREQUENCY_HZ,PLOT_MAX_FREQUENCY_HZ)
import soundcard as sc

class Panel(QObject):
    changed=Signal()
    telemetryChanged=Signal()
    plotChanged=Signal()
    def __init__(self,directory,app):
        QObject.__init__(self)
        self.app=app;self.store=Store(directory);self.engine=Engine();self.paused=False
        self.error=self.store.warning;self.device_rows=[];self.preset_name=''
        self._telemetry=self.engine.status.copy();self._closed=False;self.plots=[]
        self.save_timer=QTimer(self);self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save)
        self.edit_timer=QTimer(self);self.edit_timer.setSingleShot(True)
        self.edit_timer.timeout.connect(self.apply)
        self.poll=QTimer(self);self.poll.timeout.connect(self.tick)
        self.refreshDevices()
        cfg=self.store.current.copy()
        if not cfg['source_id']:cfg['source_id']=sc.default_speaker().id
        self.store.current=validate(cfg);self.dsp=compile_dsp(cfg);self.engine.update(self.dsp)
        self.server=Server(directory,self,self);self.poll.start(UI_REFRESH_MS)

    @Property('QVariantMap',notify=changed)
    def settings(self):return self.store.current.copy()
    @Property('QVariantList',notify=changed)
    def sources(self):return self.rows_for('source_id')
    @Property('QVariantList',notify=changed)
    def targets(self):return self.rows_for('target_id')
    def rows_for(self,key):
        other=self.store.current['target_id' if key=='source_id' else 'source_id']
        rows=[dict(id='',name='选择设备',icon='wave',supported=True,reason='',format='')]
        for device in self.device_rows:
            reason=device['reason']
            if device['id']==other:reason='已用于另一条音频路由'
            rows.append(dict(id=device['id'],name=device['name'],icon=device['icon'],supported=not reason,
                             reason=reason,format=f"{device.get('rate',0)/1000:g} kHz · {device.get('channels','?')} 声道"))
        current=self.store.current[key]
        if current and not any(d['id']==current for d in rows):rows.append(dict(id=current,name='设备未连接 · 请重新选择',icon='wave',supported=False,reason='未连接',format=''))
        return rows
    @Property('QStringList',notify=changed)
    def presets(self):return list(self.store.presets)
    @Property(str,notify=changed)
    def presetName(self):
        # A displayed selection must resolve to a saved DSP value, not a label.
        current=self.store.current
        names=list(self.store.presets)
        if self.preset_name in names:names.remove(self.preset_name);names.insert(0,self.preset_name)
        return next((name for name in names if all(current[k]==self.store.presets[name][k] for k in current if k not in ('source_id','target_id'))),'')
    @Property(str,notify=changed)
    def presetPlaceholder(self):return '尚无预设' if not self.store.presets else '未保存为预设'
    @Property(bool,notify=changed)
    def canDeletePreset(self):return self.presetName in self.store.presets
    @Property(str,notify=changed)
    def message(self):return self.error
    @Property(bool,notify=changed)
    def muted(self):return self.paused
    @Property('QVariantMap',notify=telemetryChanged)
    def telemetry(self):return self._telemetry
    @Property('QVariantList',constant=True)
    def frequencies(self):return list(EQ_FREQUENCIES_HZ)
    @Property('QVariantMap',constant=True)
    def limits(self):return dict(eq=EQ_MAX_DB,band_gain_db=list(FILTER_BAND_GAIN_DB),max_bands=MAX_FILTER_BANDS,**{k:list(v) for k,v in PARAMETER_LIMITS.items()})
    @Property(float,notify=changed)
    def headroom(self):return self.dsp['preamp_db']
    @Property('QVariantList',notify=changed)
    def filterBands(self):return [row.copy() for row in self.store.current['bands']]
    @Property(str,notify=changed)
    def filterSummary(self):
        rows=[r for r in self.store.current['bands'] if r['enabled']]
        return '；'.join(f"{r['low']:g}–{r['high']:g} Hz · {r['gain_db']:+g} dB" for r in rows) if rows else '没有启用的频段，副音频静音'
    @Property(float,notify=changed)
    def bodyRetention(self):return mid_gain(self.store.current)*100
    @Property(float,constant=True)
    def minimumBodyRetention(self):return 100*10**(-SPATIAL_MAX_MID_CUT_DB/20)
    @Slot(float)
    def setBodyRetention(self,percent):
        value=max(self.minimumBodyRetention,min(100.,percent))
        strength=-20*math.log10(value/100)/SPATIAL_MAX_MID_CUT_DB*100
        self.edit('spatial_strength',max(0.,min(100.,strength)))
    @Slot(int,str,'QVariant')
    def editFilterBand(self,index,key,value):
        if not 0<=index<len(self.store.current['bands']) or key not in ('low','high','gain_db','enabled'):return
        rows=[r.copy() for r in self.store.current['bands']];rows[index][key]=value
        self.edit('bands',rows)
    @Slot()
    def addFilterBand(self):
        if len(self.store.current['bands'])>=MAX_FILTER_BANDS:return
        rows=[r.copy() for r in self.store.current['bands']]
        rows.append(dict(low=NEW_FILTER_BAND_LOW_HZ,high=NEW_FILTER_BAND_HIGH_HZ,gain_db=0.,enabled=False))
        self.edit('bands',rows)
    @Slot(int)
    def deleteFilterBand(self,index):
        rows=self.store.current['bands']
        if len(rows)<=1 or not 0<=index<len(rows):return
        self.edit('bands',[r.copy() for i,r in enumerate(rows) if i!=index])

    @Slot()
    def refreshDevices(self):
        try:self.device_rows=devices()
        except (RuntimeError,OSError) as exc:self.error=str(exc)
        self.changed.emit()
    @Slot(str,'QVariant')
    def edit(self,key,value):
        try:
            if key in ('source_id','target_id'):
                self.control_set({key:value});self.error='';self.changed.emit();return
            if key in ('source_id','target_id') and self.engine.active:raise ValueError('停止补声后再切换设备。')
            cfg=merge_settings(self.store.current,{key:value})
            if self.store.load_failed:raise ValueError(self.store.warning)
            self.store.current=cfg;self.preset_name='';self.error=''
            self.changed.emit();self.edit_timer.start(UI_EDIT_DEBOUNCE_MS)
        except (ValueError,OSError,RuntimeError) as exc:self.error=str(exc);self.changed.emit()
    @Slot(int,float)
    def setBand(self,index,value):
        if not 0<=index<len(EQ_FREQUENCIES_HZ):return
        gains=list(self.store.current['gains']);gains[index]=round(max(-EQ_MAX_DB,min(EQ_MAX_DB,value)),1)
        self.edit('gains',gains)
    @Slot()
    def flat(self):self.edit('gains',[0.]*len(EQ_FREQUENCIES_HZ))
    @Slot()
    def swapRoutes(self):
        if self.engine.active:return
        try:
            self.control_set(dict(source_id=self.store.current['target_id'],target_id=self.store.current['source_id']))
            self.error='';self.changed.emit()
        except (ValueError,OSError,RuntimeError) as exc:self.error=str(exc);self.changed.emit()
    def apply(self):
        self.edit_timer.stop()
        try:self.dsp=compile_dsp(self.store.current)
        except ValueError as exc:
            self.store.current=self.dsp['settings'].copy();self.error='未应用：'+str(exc)
            self.changed.emit();return
        dsp=self.dsp
        if self.paused:dsp={**dsp,'settings':{**dsp['settings'],'gain':0}}
        self.engine.update(dsp)
        for plot in self.plots:plot.set_dsp(self.dsp)
        self.save_timer.start(UI_SAVE_DEBOUNCE_MS);self.changed.emit()
    def save(self):
        try:self.store.save()
        except OSError as exc:self.error='设置未保存：'+str(exc);self.changed.emit()
    def control_get(self):return self.store.current.copy()
    def control_paused(self):return self.paused
    def control_set(self,patch):
        if self.store.load_failed:raise ValueError(self.store.warning)
        cfg=merge_settings(self.store.current,patch)
        compile_dsp(cfg)
        if cfg['source_id'] and cfg['source_id']==cfg['target_id']:raise ValueError('主音频和副音频必须是不同设备。')
        resume=prepare_auxiliary_switch(self.engine,self.store.current,cfg)
        if 'source_id' in patch and cfg['source_id']!=self.store.current['source_id'] and cfg['source_id']:
            sync_main_output(cfg['source_id'])
        self.store.current=cfg;self.preset_name='';self.apply()
        self.store.save()
        if resume:self.engine.start(self.engine.dsp)
        return self.control_get()
    def control_pause(self,value):self.paused=value;self.apply()
    def control_start(self):
        if not self.engine.active:
            cfg=self.store.current
            if not cfg['target_id'] or cfg['target_id']==cfg['source_id']:raise ValueError('请选择不同的主音频和副音频设备。')
            sync_main_output(cfg['source_id']);self.apply();self.engine.start(self.engine.dsp)
    def control_close(self):self.close();self.app.quit()
    @Slot()
    def toggle(self):
        try:
            if self.engine.active:self.engine.stop()
            else:self.control_start()
            self.error=''
        except (ValueError,RuntimeError) as exc:self.error=str(exc)
        self.tick();self.changed.emit()
    @Slot()
    def toggleMute(self):self.control_pause(not self.paused)
    @Slot(str)
    def usePreset(self,name):
        try:
            cfg=self.store.presets[name].copy()
            cfg.update({k:self.store.current[k] for k in ('source_id','target_id')})
            self.control_set(cfg);self.preset_name=name;self.error='';self.changed.emit()
        except (ValueError,OSError,KeyError) as exc:self.error=str(exc);self.changed.emit()
    @Slot()
    def savePreset(self):
        name,ok=QInputDialog.getText(None,'新增预设','将当前声音设置保存为：')
        if not ok:return
        name=name.strip()
        try:
            self.control_add_preset(name);self.error=''
        except (ValueError,OSError) as exc:self.error=str(exc)
        self.changed.emit()
    def control_add_preset(self,name):
        result=self.store.add_preset(name);self.preset_name=result['name'];self.changed.emit();return result
    def control_delete_preset(self,name):
        result=self.store.delete_preset(name)
        if self.preset_name==name:self.preset_name=''
        self.changed.emit();return result
    @Slot()
    def deletePreset(self):
        if not self.canDeletePreset:return
        name=self.presetName
        if QMessageBox.question(None,'删除预设',f'删除“{name}”？当前声音设置会保留。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:self.control_delete_preset(name);self.error=''
        except (ValueError,OSError) as exc:self.error=str(exc)
        self.changed.emit()
    @Slot()
    def showSystemEffects(self):
        cfg=self.store.current
        QMessageBox.information(None,'本机音效 · 只读检查',report_text(effects_report(cfg['source_id'],cfg['target_id'])))
    @Slot()
    def importPreset(self):
        path,_=QFileDialog.getOpenFileName(None,'导入预设','','JSON (*.json)')
        if not path:return
        try:
            cfg=self.store.import_file(path)
            cfg.update({k:self.store.current[k] for k in ('source_id','target_id')})
            self.control_set(cfg);self.error=''
        except (ValueError,OSError,KeyError,TypeError) as exc:self.error='导入失败：'+str(exc)
        self.changed.emit()
    @Slot()
    def exportPreset(self):
        path,_=QFileDialog.getSaveFileName(None,'导出预设','DualTone-preset.json','JSON (*.json)')
        if not path:return
        try:self.store.export(path,self.store.current);self.error=''
        except (ValueError,OSError) as exc:self.error='导出失败：'+str(exc)
        self.changed.emit()
    @Slot(bool)
    def setVisible(self,value):
        self.engine.analysis_enabled=value
        if not value:self.engine.analysis_packets.clear()
    def tick(self):
        self._telemetry={**self.engine.status,'active':self.engine.active}
        if self.engine.analysis_enabled:
            visible=[p for p in self.plots if p.window() and p.window().isVisible()]
            if visible:
                visible[0].analyze(self.engine)
                for plot in visible[1:]:plot.spectra=visible[0].spectra;plot.update()
        self.telemetryChanged.emit()
    def close(self):
        if self._closed:return
        self._closed=True;self.poll.stop()
        if self.edit_timer.isActive():self.apply()
        self.edit_timer.stop();self.save_timer.stop()
        self.engine.stop();self.save();self.server.close()

class AudioPlot(QQuickPaintedItem):
    """Response coordinates are dB; spectrum uses a separate dBFS scale."""
    selectedChanged=Signal()
    compactChanged=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.panel=None;self.dsp=None;self.selected=-1
        self.frequencies=np.geomspace(PLOT_MIN_FREQUENCY_HZ,PLOT_MAX_FREQUENCY_HZ,SPECTRUM_DISPLAY_POINTS)
        self.response=np.zeros(SPECTRUM_DISPLAY_POINTS)
        self.eq_response=np.zeros(SPECTRUM_DISPLAY_POINTS)
        self.spectra=[];self.setAntialiasing(True)
        self._compact=False
        self.drag_origin_y=0.;self.drag_origin_gain=0.
    @Property(bool,notify=compactChanged)
    def compact(self):return self._compact
    @compact.setter
    def compact(self,value):self._compact=value;self.compactChanged.emit();self.update()
    @Property(int,notify=selectedChanged)
    def selectedBand(self):return self.selected
    @Slot(QObject)
    def attach(self,panel):
        self.panel=panel;panel.plots.append(self);self.set_dsp(panel.dsp)
    def set_dsp(self,dsp):
        self.dsp=dsp;h=np.ones(len(self.frequencies),complex)
        if dsp['settings']['eq_enabled']:h*=sosfreqz(dsp['eq']['sos'],worN=self.frequencies,fs=TARGET_RATE_HZ)[1]
        self.eq_response=np.clip(20*np.log10(np.maximum(abs(h),1e-12)),-36,12)
        h*=band_response(dsp['band'],self.frequencies)
        self.response=np.clip(20*np.log10(np.maximum(abs(h),1e-12)),-36,12);self.update()
    def analyze(self,engine):
        rows=list(engine.analysis_packets)
        if not rows or not engine.active or engine.status['input_peak']==0:
            self.spectra=[];self.update();return
        n=SPECTRUM_FFT_FRAMES;window=np.hanning(n);freq=np.fft.rfftfreq(n,1/TARGET_RATE_HZ)
        spectra=[]
        for channel in (0,1):
            packet=np.concatenate([r[channel] for r in rows])[-n:]
            padded=np.zeros((n,CHANNEL_COUNT));padded[-len(packet):]=packet
            # Max channel magnitude avoids anti-phase stereo cancellation.
            magnitude=np.max(abs(np.fft.rfft(padded*window[:,None],axis=0)),axis=1)*2/window.sum()
            # Peak-bin reduction preserves narrow tones on a logarithmic axis.
            # Interpolating dB at sparse points missed a 0 dBFS tone by 10 dB.
            centers=self.frequencies;edges=np.sqrt(centers[:-1]*centers[1:])
            bins=np.searchsorted(edges,freq)
            in_range=(freq>=centers[0]) & (freq<=centers[-1])
            reduced=np.interp(centers,freq,magnitude)
            np.maximum.at(reduced,bins[in_range],magnitude[in_range])
            spectra.append(20*np.log10(np.maximum(reduced,10**(SPECTRUM_FLOOR_DB/20))))
        self.spectra=spectra;self.update()
    def box(self):return QRectF(38,26,max(1,self.width()-76),max(1,self.height()-54))
    def px(self,f):
        b=self.box();return b.left()+math.log10(f/20)/3*b.width()
    def py(self,db):
        b=self.box();return b.top()+(12-db)/48*b.height()
    @Slot(float,result=float)
    def bandPosition(self,frequency):return self.px(frequency)
    @Slot(result=float)
    def minimumBandSpacing(self):return min(self.px(b)-self.px(a) for a,b in zip(EQ_FREQUENCIES_HZ,EQ_FREQUENCIES_HZ[1:]))
    @Slot()
    def resetSelected(self):
        if self.selected>=0 and self.panel and self.dsp['settings']['eq_enabled']:self.panel.setBand(self.selected,0)
    @Slot(int)
    def stepSelected(self,step):
        self.selected=max(0,min(len(EQ_FREQUENCIES_HZ)-1,self.selected+step));self.selectedChanged.emit();self.update()
    @Slot(float)
    def adjustSelected(self,delta):
        if self.selected>=0 and self.panel and self.dsp['settings']['eq_enabled']:self.panel.setBand(self.selected,self.panel.settings['gains'][self.selected]+delta)
    @Slot(float,float)
    def selectAt(self,x,y):
        if not self.dsp or not self.dsp['settings']['eq_enabled']:return
        self.selected=min(range(len(EQ_FREQUENCIES_HZ)),key=lambda i:abs(self.px(EQ_FREQUENCIES_HZ[i])-x))
        self.drag_origin_y=y;self.drag_origin_gain=self.panel.settings['gains'][self.selected]
        self.selectedChanged.emit();self.update()
    @Slot(float)
    def dragTo(self,y):
        if self.selected<0 or not self.panel or not self.dsp['settings']['eq_enabled']:return
        b=self.box();self.panel.setBand(self.selected,self.drag_origin_gain+(self.drag_origin_y-y)/b.height()*48)
    def paint(self,p):
        p.setRenderHint(QPainter.Antialiasing);b=self.box()
        p.fillRect(self.boundingRect(),QColor('#182024'));p.setFont(QFont('Segoe UI',8))
        for db in (-36,-24,-12,0,12):
            p.setPen(QPen(QColor('#4a565d' if db==0 else '#2d383e'),1))
            p.drawLine(int(b.left()),int(self.py(db)),int(b.right()),int(self.py(db)))
            p.setPen(QColor('#a4b4bd'));p.drawText(QRectF(2,self.py(db)-8,29,16),Qt.AlignRight|Qt.AlignVCenter,f'{db:+d}')
        for f in (32,125,500,2000,8000):
            x=self.px(f);p.setPen(QColor('#2d383e'));p.drawLine(int(x),int(b.top()),int(x),int(b.bottom()))
            p.setPen(QColor('#a4b4bd'));p.drawText(QRectF(x-20,b.bottom()+5,40,18),Qt.AlignCenter,f'{f/1000:g}k' if f>=1000 else str(f))
        p.setPen(QColor('#a4b4bd'));p.drawText(5,15,'dB');p.drawText(int(b.right()+4),15,'dBFS')
        for db in (0,-30,-60,-90):
            y=b.top()+db/SPECTRUM_FLOOR_DB*b.height()
            p.drawText(QRectF(b.right()+5,y-8,30,16),Qt.AlignLeft|Qt.AlignVCenter,str(db))
        p.save();p.setClipRect(b)
        for data,color in zip(self.spectra,('#8d9da9','#5bd6c1')):
            path=QPainterPath();path.moveTo(b.left(),b.bottom())
            for f,db in zip(self.frequencies,data):path.lineTo(self.px(f),b.bottom()-np.clip((db-SPECTRUM_FLOOR_DB)/-SPECTRUM_FLOOR_DB,0,1)*b.height())
            path.lineTo(b.right(),b.bottom());path.closeSubpath()
            fill=QColor(color);fill.setAlpha(33);p.fillPath(path,fill);p.setPen(QPen(QColor(color),1));p.drawPath(path)
        if not self._compact and self.dsp and self.dsp['band'] is not None:
            filtered=QPainterPath();filtered.moveTo(self.px(self.frequencies[0]),self.py(self.response[0]))
            for f,db in zip(self.frequencies[1:],self.response[1:]):filtered.lineTo(self.px(f),self.py(db))
            p.setPen(QPen(QColor('#a5a481'),1.5,Qt.DashLine));p.drawPath(filtered)
        response=self.response if self._compact else self.eq_response
        path=QPainterPath();path.moveTo(self.px(self.frequencies[0]),self.py(response[0]))
        for f,db in zip(self.frequencies[1:],response[1:]):path.lineTo(self.px(f),self.py(db))
        p.setPen(QPen(QColor('#f3c969'),2));p.drawPath(path)
        if not self._compact and self.dsp and self.dsp['settings']['eq_enabled']:
            p.setPen(QPen(QColor('#f3c969'),1.5));p.setBrush(QColor('#182024'))
            for i,f in enumerate(EQ_FREQUENCIES_HZ):
                db=self.dsp['settings']['gains'][i]
                radius=7 if i==self.selected else 5
                p.setBrush(QColor('#f3c969' if i==self.selected else '#182024'))
                p.drawEllipse(self.px(f)-radius,self.py(db)-radius,2*radius,2*radius)
        p.restore()
