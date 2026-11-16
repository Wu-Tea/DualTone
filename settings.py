"""Portable, validated application settings and user presets."""
import json, math, os, shutil
from pathlib import Path
from config import (SETTINGS_VERSION,SETTINGS_MAX_BYTES,PRESET_MAX_COUNT,PRESET_NAME_MAX_CHARS,
    DEVICE_ID_MAX_CHARS,PARAMETER_LIMITS,EQ_MAX_DB,EQ_FREQUENCIES_HZ,
    SUPPLEMENT_GAIN_PERCENT,SUPPLEMENT_LOW_HZ,SUPPLEMENT_HIGH_HZ,MAX_FILTER_BANDS,FILTER_BAND_GAIN_DB,
    SPATIAL_MODES,SPATIAL_DEFAULT_STRENGTH_PERCENT)

DEFAULT = dict(source_id='', target_id='', gain=SUPPLEMENT_GAIN_PERCENT, eq_enabled=True,
               gains=[0.0]*len(EQ_FREQUENCIES_HZ), band_enabled=True, low=SUPPLEMENT_LOW_HZ, high=SUPPLEMENT_HIGH_HZ,bands=None,
               spatial_mode='space',spatial_strength=SPATIAL_DEFAULT_STRENGTH_PERCENT)

def validate_bands(rows):
    if not isinstance(rows,list) or not 1<=len(rows)<=MAX_FILTER_BANDS:raise ValueError(f'频段数量必须为 1–{MAX_FILTER_BANDS}。')
    result=[]
    for index,row in enumerate(rows):
        if not isinstance(row,dict) or set(row)-{'low','high','gain_db','enabled'}:raise ValueError('频段配置字段无效。')
        band={'gain_db':0.0,'enabled':True,**row}
        for key,limits in (('low',PARAMETER_LIMITS['low']),('high',PARAMETER_LIMITS['high']),('gain_db',FILTER_BAND_GAIN_DB)):
            value=band.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or not limits[0]<=value<=limits[1]:raise ValueError(f'频段 {index+1} 的 {key} 超出范围。')
            band[key]=float(value)
        if band['low']>=band['high']:raise ValueError(f'频段 {index+1} 的下限必须小于上限。')
        if type(band['enabled']) is not bool:raise ValueError('频段开关必须为布尔值。')
        result.append(band)
    return result

def merge_settings(current,patch):
    if not isinstance(patch,dict):raise ValueError('设置补丁必须是对象。')
    patch=patch.copy()
    # Legacy CLI low/high edits target the first range; bands is canonical.
    if 'bands' not in patch and any(k in patch for k in ('low','high')):
        rows=[row.copy() for row in current['bands']]
        rows[0].update({k:patch[k] for k in ('low','high') if k in patch});patch['bands']=rows
    return validate({**current,**patch})
def validate(value):
    if not isinstance(value,dict): raise ValueError('配置必须是 JSON 对象。')
    # Old original-mode presets retain their sound as 100% body retention.
    # The application now has one spatial path, with no mode selector.
    if value.get('spatial_mode')=='original':value={**value,'spatial_mode':'space','spatial_strength':0.0}
    if set(value)-set(DEFAULT): raise ValueError('配置包含不支持的设置。')
    result={**DEFAULT,**value}
    if result['spatial_mode'] not in SPATIAL_MODES:raise ValueError('副路使用 space 空间补充。')
    rows=result['bands']
    if rows is None:rows=[dict(low=result['low'],high=result['high'],gain_db=0.0,enabled=True)]
    result['bands']=validate_bands(rows)
    result['low']=result['bands'][0]['low'];result['high']=result['bands'][0]['high']
    for key in ('source_id','target_id'):
        if not isinstance(result[key],str) or len(result[key])>DEVICE_ID_MAX_CHARS:
            raise ValueError('设备标识无效。')
    for key in ('eq_enabled','band_enabled'):
        if type(result[key]) is not bool: raise ValueError('开关值必须为 true 或 false。')
    for key,(lo,hi) in PARAMETER_LIMITS.items():
        x=result[key]
        if type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi:
            raise ValueError(f'{key} 超出允许范围。')
        result[key]=float(x)
    if result['low']>=result['high']: raise ValueError('频段下限必须小于上限。')
    gains=result['gains']
    if not isinstance(gains,(list,tuple)) or len(gains)!=len(EQ_FREQUENCIES_HZ):
        raise ValueError('EQ 需要 10 个频段。')
    if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>EQ_MAX_DB for v in gains):
        raise ValueError('EQ 增益必须在 −12 到 +12 dB 之间。')
    result['gains']=[float(v) for v in gains]
    return result

def save_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temporary,path)

def read_json(path):
    path=Path(path)
    if path.stat().st_size>SETTINGS_MAX_BYTES: raise ValueError('配置文件过大，最多支持 128 KB。')
    return json.loads(path.read_text(encoding='utf-8-sig'))

class Store:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.current=validate(DEFAULT)
        self.presets={}
        self.warning=''
        self.load_failed=False
        self.migrate_from_v1=False
        path=self.directory/'settings.json'
        if path.exists():
            try:
                doc=read_json(path)
                if not isinstance(doc,dict) or doc.get('version') not in (1,SETTINGS_VERSION):raise ValueError('不支持的配置版本。')
                self.migrate_from_v1=doc['version']==1
                current=validate(doc['current'])
                presets=doc.get('presets',{})
                if not isinstance(presets,dict) or len(presets)>PRESET_MAX_COUNT:raise ValueError('预设列表无效。')
                for name,values in presets.items():
                    if not isinstance(name,str) or not 1<=len(name)<=PRESET_NAME_MAX_CHARS:raise ValueError('预设名称无效。')
                    presets[name]=validate(values)
                self.current=current;self.presets=presets
            except (OSError,ValueError,KeyError,TypeError) as exc:
                self.warning=f'旧配置未能读取，已载入默认值。原文件保留：{exc}'
                self.load_failed=True
    def save(self):
        # Preserve a malformed user file instead of silently overwriting it.
        if self.load_failed:return
        self._write(self.presets)
    def _write(self,presets):
        path=self.directory/'settings.json'
        if self.migrate_from_v1 and path.exists():
            backup=self.directory/'settings.v1.backup.json'
            if not backup.exists():shutil.copy2(path,backup)
        save_json(path,dict(version=SETTINGS_VERSION,current=self.current,presets=presets))
        self.migrate_from_v1=False
    def export(self,path,settings):save_json(path,dict(version=SETTINGS_VERSION,settings=validate(settings)))
    def add_preset(self,name):
        if self.load_failed:raise ValueError(self.warning)
        if not isinstance(name,str) or not 1<=len(name.strip())<=PRESET_NAME_MAX_CHARS:raise ValueError('请输入有效的预设名称。')
        name=name.strip()
        if name in self.presets:raise ValueError('名称已存在，请使用新名称。')
        if len(self.presets)>=PRESET_MAX_COUNT:raise ValueError('预设数量已达上限。')
        presets={**self.presets,name:validate(self.current)}
        self._write(presets)
        self.presets=presets
        return dict(name=name,settings=self.presets[name])
    def delete_preset(self,name):
        if self.load_failed:raise ValueError(self.warning)
        if name not in self.presets:raise ValueError('自定义预设不存在。')
        presets={k:v for k,v in self.presets.items() if k!=name}
        self._write(presets)
        self.presets=presets
        return dict(deleted=name)
    def import_file(self,path):
        doc=read_json(path)
        if not isinstance(doc,dict) or doc.get('version') not in (1,SETTINGS_VERSION):raise ValueError('不支持的预设文件。')
        return validate(doc['settings'])
