"""AI/script-friendly CLI. stdout is UTF-8 JSON; failures use nonzero exit codes."""
import sys,json,argparse,subprocess,time
from pathlib import Path
ROOT=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).parent
if not getattr(sys,'frozen',False):sys.path.insert(0,str(ROOT/'lib'))
from PySide6.QtCore import QCoreApplication
from control import request,NotRunning,Server,HeadlessHost
from audio_engine import devices,compile_dsp
from settings import Store,validate,merge_settings,read_json,save_json
from config import SETTINGS_VERSION,IPC_TIMEOUT_MS,PARAMETER_LIMITS,EQ_FREQUENCIES_HZ,EQ_MAX_DB,MAX_FILTER_BANDS,FILTER_BAND_GAIN_DB
from config import SPATIAL_MODES,SPATIAL_MAX_MID_CUT_DB,SPATIAL_TRANSITION_MS
from routing import sync_main_output
from system_effects import effects_report

def emit(value):
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False,indent=2))

def main():
    p=argparse.ArgumentParser(description='DualTone 控制接口。stdout=UTF-8 JSON；成功=0，失败=1。')
    p.add_argument('--data-dir',type=Path,default=ROOT/'data',help='配置目录；用于选择要控制的实例')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('devices','presets','get','status','start','stop','shutdown','serve','schema','effects'):sub.add_parser(name)
    for name in ('preset-add','preset-delete'):sub.add_parser(name).add_argument('name')
    s=sub.add_parser('latency',help='测量正在运行的双路数字转发延迟，结果不含声学/设备内部延迟')
    s.add_argument('--probe',action='store_true',help='播放约四秒低音量测试信号；默认只分析正在播放的声音')
    s=sub.add_parser('set');g=s.add_mutually_exclusive_group(required=True);g.add_argument('--json');g.add_argument('--file',type=Path)
    s=sub.add_parser('preset');s.add_argument('name')
    s=sub.add_parser('pause');s.add_argument('enabled',choices=['on','off'])
    for name in ('import','export'):
        s=sub.add_parser(name);s.add_argument('file',type=Path)
    args=p.parse_args();app=QCoreApplication(sys.argv[:1]);directory=args.data_dir.resolve()
    try:
        if args.command=='serve':
            host=HeadlessHost(directory,app);server=Server(directory,host)
            app.aboutToQuit.connect(host.engine.stop)
            code=app.exec();server.close();return code
        if args.command=='devices':emit(dict(ok=True,result=devices()));return 0
        if args.command=='latency':
            state=request(directory,'status')
            if not state.get('ok'):raise ValueError(state.get('error'))
            if state['result']['audio']['state']!='running' or state['result']['paused']:raise ValueError('请先启动副音频并取消静音。')
            from measure_latency import measure
            result=measure(state['result']['settings'],probe=args.probe)
            after=request(directory,'status')
            if not after.get('ok') or after['result']['audio']['state']!='running' or after['result']['paused'] or after['result']['settings']!=state['result']['settings']:
                raise ValueError('测量期间音频状态或设置改变，请重新测量。')
            emit(dict(ok=True,result=result));return 0
        if args.command=='schema':
            emit(dict(ok=True,result=dict(version=SETTINGS_VERSION,defaults=validate({}),limits=PARAMETER_LIMITS,
                eq_frequencies_hz=EQ_FREQUENCIES_HZ,eq_gain_range_db=[-EQ_MAX_DB,EQ_MAX_DB],
                spatial=dict(modes=list(SPATIAL_MODES),strength_percent=list(PARAMETER_LIMITS['spatial_strength']),
                    max_mid_cut_db=SPATIAL_MAX_MID_CUT_DB,transition_ms=SPATIAL_TRANSITION_MS,
                    ui_body_retention_percent='100 * 10 ** (-max_mid_cut_db * spatial_strength / 100 / 20)',
                    legacy_original='Accepted for old configurations; normalized to space with strength 0 (100% body).',
                    added_buffer_frames=0,semantics='Auxiliary only: attenuate Mid, retain Side; no voice or surround extraction.'),
                filter_bands=dict(min_count=1,max_count=MAX_FILTER_BANDS,gain_db=list(FILTER_BAND_GAIN_DB),
                    fields=['low','high','gain_db','enabled'],low_hz=PARAMETER_LIMITS['low'],high_hz=PARAMETER_LIMITS['high'],
                    semantics='Parallel weighted bandpasses; low < high. All disabled = silence when band_enabled. Global off = bypass.',
                    legacy='low/high patch edits the first band only; bands replaces the complete list.'),
                scope='All DSP settings affect the auxiliary output only.',
                routing='Selecting source_id or starting playback synchronizes Windows console/multimedia defaults; communications is unchanged.',
                commands=['devices','get','set','presets','preset','preset-add','preset-delete','effects','start','stop','status','latency','pause','import','export','shutdown','serve'])))
            return 0
        command=args.command;arguments={}
        if command=='set':arguments=read_json(args.file) if args.file else json.loads(args.json)
        if command=='preset':arguments={'name':args.name}
        if command in ('preset-add','preset-delete'):arguments={'name':args.name}
        if command=='pause':arguments={'enabled':args.enabled=='on'}
        if command=='import':
            imported=Store(directory).import_file(args.file)
            # Import DSP only; device IDs are machine-local and must be explicitly set.
            arguments={k:v for k,v in imported.items() if k not in ('source_id','target_id')};command='set'
        if command=='export':command='get'
        if not isinstance(arguments,dict):raise ValueError('设置补丁必须是 JSON 对象。')
        try:response=request(directory,command,arguments)
        except NotRunning:
            if command=='start':
                directory.mkdir(parents=True,exist_ok=True)
                launch=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve())]
                with (directory/'service.log').open('ab') as log:
                    process=subprocess.Popen(launch+['--data-dir',str(directory),'serve'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                                             creationflags=subprocess.CREATE_NO_WINDOW)
                deadline=time.monotonic()+IPC_TIMEOUT_MS/1000
                while True:
                    try:response=request(directory,command,arguments);break
                    except NotRunning:
                        if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('后台服务未启动，请查看 data/service.log。')
                        time.sleep(.05)
            elif command in ('get','set','preset','presets','preset-add','preset-delete','effects'):
                store=Store(directory)
                if store.load_failed:raise ValueError(store.warning)
                if command=='get':result=store.current
                elif command=='presets':result=store.presets
                elif command=='preset-add':result=store.add_preset(args.name)
                elif command=='preset-delete':result=store.delete_preset(args.name)
                elif command=='effects':result=effects_report(store.current['source_id'],store.current['target_id'])
                else:
                    if command=='preset':
                        presets=store.presets
                        if args.name not in presets:raise ValueError('预设不存在。')
                        arguments={k:v for k,v in presets[args.name].items() if k not in ('source_id','target_id')}
                    cfg=merge_settings(store.current,arguments);compile_dsp(cfg)
                    if cfg['source_id'] and cfg['source_id']==cfg['target_id']:raise ValueError('主音频和副音频必须是不同设备。')
                    if 'source_id' in arguments and cfg['source_id']!=store.current['source_id'] and cfg['source_id']:sync_main_output(cfg['source_id'])
                    store.current=cfg;store.save();result=cfg
                response=dict(ok=True,offline=True,result=result)
            elif command=='status':response=dict(ok=True,result=dict(running=False,audio=dict(state='offline')))
            else:raise
        if args.command=='export' and response.get('ok'):
            save_json(args.file,dict(version=SETTINGS_VERSION,settings=response['result']))
            response=dict(ok=True,result=dict(exported=str(args.file.resolve())))
        emit(response);return 0 if response.get('ok') else 1
    except Exception as exc:emit(dict(ok=False,error=str(exc)));return 1

if __name__=='__main__':sys.exit(main())
