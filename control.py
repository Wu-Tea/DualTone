"""Versioned local JSON control over a current-user-only Windows named pipe.

GUI and headless hosts expose the same commands. No TCP listener, credentials,
shell commands, or arbitrary code execution are accepted by this protocol.
"""
import hashlib,json
from pathlib import Path
from PySide6.QtCore import QObject,QTimer
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from config import IPC_PROTOCOL_VERSION,IPC_MAX_BYTES,IPC_TIMEOUT_MS
from settings import Store,validate,merge_settings
from audio_engine import Engine,compile_dsp,devices
import soundcard as sc
from routing import sync_main_output,prepare_auxiliary_switch
from system_effects import effects_report

class NotRunning(ConnectionError):pass

def pipe_name(directory):
    key=str(Path(directory).resolve()).casefold().encode('utf-8')
    return 'DualTone-'+hashlib.sha256(key).hexdigest()[:24]

def request(directory,command,arguments=None):
    socket=QLocalSocket();socket.connectToServer(pipe_name(directory))
    if not socket.waitForConnected(IPC_TIMEOUT_MS):raise NotRunning('没有运行中的 DualTone；使用 start 启动后台服务，或打开界面。')
    data=json.dumps(dict(version=IPC_PROTOCOL_VERSION,command=command,arguments=arguments or {}),ensure_ascii=False).encode('utf-8')+b'\n'
    if len(data)>IPC_MAX_BYTES:raise ValueError('请求过大。')
    socket.write(data)
    if socket.bytesToWrite() and not socket.waitForBytesWritten(IPC_TIMEOUT_MS):raise RuntimeError('控制请求发送失败。')
    response=bytearray()
    while b'\n' not in response:
        if not socket.bytesAvailable() and not socket.waitForReadyRead(IPC_TIMEOUT_MS):raise RuntimeError('控制请求未收到完整响应。')
        response.extend(bytes(socket.readAll()))
        if len(response)>IPC_MAX_BYTES:raise ValueError('控制响应过大。')
    socket.disconnectFromServer()
    return json.loads(response.split(b'\n',1)[0])

class Server(QObject):
    def __init__(self,directory,host,parent=None):
        super().__init__(parent);self.host=host;self.clients=set();self.server=QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        if not self.server.listen(pipe_name(directory)):
            raise RuntimeError('无法启动本地控制接口：'+self.server.errorString()+'。若同一配置目录已有实例，请通过 CLI 控制或先 shutdown。')
        self.server.newConnection.connect(self.connected)
    def connected(self):
        while self.server.hasPendingConnections():
            client=self.server.nextPendingConnection();self.clients.add(client);buffer=bytearray()
            deadline=QTimer(client);deadline.setSingleShot(True);deadline.timeout.connect(client.abort);deadline.start(IPC_TIMEOUT_MS)
            client.readyRead.connect(lambda c=client,b=buffer:self.read(c,b))
            client.disconnected.connect(lambda c=client:self.drop(c))
    def drop(self,client):self.clients.discard(client);client.deleteLater()
    def read(self,client,buffer):
        buffer.extend(bytes(client.readAll()))
        if len(buffer)>IPC_MAX_BYTES:client.abort();return
        if b'\n' not in buffer:return
        try:
            doc=json.loads(buffer.split(b'\n',1)[0])
            if not isinstance(doc,dict) or doc.get('version')!=IPC_PROTOCOL_VERSION:raise ValueError('不支持的控制协议版本。')
            args=doc.get('arguments',{})
            if not isinstance(args,dict):raise ValueError('arguments 必须是对象。')
            result=self.dispatch(doc.get('command'),args)
            response=dict(ok=True,version=IPC_PROTOCOL_VERSION,result=result)
        except Exception as exc:response=dict(ok=False,version=IPC_PROTOCOL_VERSION,error=str(exc))
        client.write(json.dumps(response,ensure_ascii=False).encode('utf-8')+b'\n');client.flush();client.disconnectFromServer()
    def dispatch(self,command,args):
        host=self.host
        if command=='status':return dict(running=True,audio=host.engine.status.copy(),settings=host.control_get(),paused=host.control_paused())
        if command=='get':return host.control_get()
        if command=='presets':return host.store.presets
        if command=='preset-add':return host.control_add_preset(args.get('name'))
        if command=='preset-delete':return host.control_delete_preset(args.get('name'))
        if command=='effects':
            cfg=host.control_get();return effects_report(cfg['source_id'],cfg['target_id'])
        if command=='set':return host.control_set(args)
        if command=='preset':
            name=args.get('name');presets=host.store.presets
            if name not in presets:raise ValueError('预设不存在。')
            cfg=presets[name].copy();current=host.control_get()
            cfg.update(source_id=current['source_id'],target_id=current['target_id'])
            return host.control_set(cfg)
        if command=='start':host.control_start();return host.engine.status.copy()
        if command=='stop':
            if not host.engine.stop():raise RuntimeError('音频线程仍在停止，请查看 status。')
            return host.engine.status.copy()
        if command=='pause':
            if type(args.get('enabled')) is not bool:raise ValueError('enabled 必须为布尔值。')
            host.control_pause(args['enabled']);return dict(paused=host.control_paused())
        if command=='shutdown':QTimer.singleShot(100,host.control_close);return dict(shutting_down=True)
        raise ValueError('未知命令。')
    def close(self):
        self.server.close()
        for c in list(self.clients):c.abort()

class HeadlessHost:
    def __init__(self,directory,app):
        self.store=Store(directory);self.engine=Engine();self.app=app;self.paused=False
        if self.store.load_failed:raise ValueError(self.store.warning)
        cfg=self.store.current.copy()
        if not cfg['source_id']:cfg['source_id']=sc.default_speaker().id
        self.store.current=validate(cfg)
    def control_get(self):return self.store.current.copy()
    def control_paused(self):return self.paused
    def control_pause(self,value):self.paused=value;self.engine.update(self.compiled())
    def compiled(self):
        dsp=compile_dsp(self.store.current)
        if self.paused:dsp={**dsp,'settings':{**dsp['settings'],'gain':0}}
        return dsp
    def control_set(self,patch):
        cfg=merge_settings(self.store.current,patch)
        compile_dsp(cfg)
        if cfg['source_id'] and cfg['source_id']==cfg['target_id']:raise ValueError('主音频和副音频必须是不同设备。')
        resume=prepare_auxiliary_switch(self.engine,self.store.current,cfg)
        if 'source_id' in patch and cfg['source_id']!=self.store.current['source_id'] and cfg['source_id']:
            sync_main_output(cfg['source_id'])
        self.store.current=cfg;self.store.save();self.engine.update(self.compiled())
        if resume:self.engine.start(self.engine.dsp)
        return self.control_get()
    def control_add_preset(self,name):return self.store.add_preset(name)
    def control_delete_preset(self,name):return self.store.delete_preset(name)
    def control_start(self):
        if not self.engine.active:
            cfg=self.store.current
            if not cfg['target_id'] or cfg['source_id']==cfg['target_id']:raise ValueError('请选择不同的主音频和副音频设备。')
            sync_main_output(cfg['source_id']);self.engine.start(self.compiled())
    def control_close(self):self.engine.stop();self.app.quit()
