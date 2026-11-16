"""Read-only registry/config evidence; never claims an APO is executing."""
import os,re,winreg
from pathlib import Path

RENDER_KEY=r'SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render'
GUID_PATTERN=r'\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}'

def endpoint_effects(device_id):
    ids=re.findall(GUID_PATTERN,device_id)
    if not ids:return dict(state='unknown',modules=[],note='未选择设备')
    modules=set();unresolved=set()
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,RENDER_KEY+'\\'+ids[-1]+r'\FxProperties') as key:
            count=winreg.QueryInfoKey(key)[1]
            for index in range(count):
                _,value,_=winreg.EnumValue(key,index)
                for clsid in re.findall(GUID_PATTERN,str(value)):
                    if clsid=='{00000000-0000-0000-0000-000000000000}':continue
                    try:
                        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,'CLSID\\'+clsid+r'\InprocServer32') as server:
                            path=winreg.QueryValueEx(server,None)[0]
                            modules.add(os.path.expandvars(path))
                    except FileNotFoundError:unresolved.add(clsid)
        return dict(state='read',modules=sorted(modules),unresolved=sorted(unresolved),
                    equalizer_apo_registered=any('equalizerapo' in m.lower() for m in modules),
                    note='这是设备注册配置；无法仅凭注册表确认当前音效正在运行。')
    except FileNotFoundError:return dict(state='read',modules=[],equalizer_apo_registered=False,note='未发现设备音效注册项。')
    except OSError as exc:return dict(state='unknown',modules=[],note='无法读取设备音效配置：'+str(exc))

def effects_report(source_id,target_id):
    installed=False;config_path=None;summary=[];config_error=''
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\EqualizerAPO') as key:
            installed=True;config_path=Path(winreg.QueryValueEx(key,'ConfigPath')[0])/'config.txt'
        content=config_path.read_text(encoding='utf-8-sig')
        for line in content.splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            if line.startswith('Filter:'):summary.append(line)
            elif line.startswith('Include:'):summary.append(line)
            elif line.startswith('VSTPlugin:'):
                match=re.search(r'Library\s+(?:"([^"]+)"|(\S+))',line)
                if match:summary.append('VST: '+Path(match[1] or match[2]).name+('（配置旁路）' if 'Bypass 1' in line else ''))
    except FileNotFoundError:
        if installed:config_error='配置文件未找到。'
    except OSError as exc:config_error='无法读取配置：'+str(exc)
    return dict(equalizer_apo_installed=installed,config_path=str(config_path) if config_path else None,
                configured_processing=summary,config_error=config_error,
                main=endpoint_effects(source_id),auxiliary=endpoint_effects(target_id),
                scope='只读检查；安装、配置、设备挂载不等于实时生效，未检测应用内 EQ 或显示器内部音效。')

def report_text(report):
    lines=[]
    for label,key in [('主音频','main'),('副音频','auxiliary')]:
        row=report[key]
        status='已发现 Equalizer APO 挂载配置' if row.get('equalizer_apo_registered') else ('未发现 Equalizer APO 挂载配置' if row['state']=='read' else '无法确认')
        lines.append(label+'：'+status)
        if row['modules']:lines.append('设备音效模块：'+', '.join(Path(m).name for m in row['modules']))
    if report['equalizer_apo_installed']:
        lines.extend(['','本机已安装 Equalizer APO；配置文件中存在：',*report['configured_processing']])
    else:lines.extend(['','未发现 Equalizer APO 安装信息。'])
    if report['config_error']:lines.append(report['config_error'])
    lines.extend(['',report['scope'],'DualTone 的均衡器与频段过滤只处理副音频；它们不会关闭其他软件或设备中的音效。'])
    return '\n'.join(lines)
