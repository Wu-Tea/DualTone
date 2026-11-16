"""Explicit default-render routing; does not render or delay the main stream."""
from soundcard import mediafoundation as mf

E_CONSOLE=0
E_MULTIMEDIA=1
E_COMMUNICATIONS=2
PLAYBACK_ROLES=(E_CONSOLE,E_MULTIMEDIA)
CLSID_POLICY_CONFIG='{870af99c-171d-4f9e-af0d-e63df40c2bc9}'
IID_POLICY_CONFIG='{f8679f50-850a-41cf-9c72-430f290290c8}'
CLSCTX_ALL=23
# IPolicyConfig's ABI matches the interface used by pycaw. Reuse the existing
# COM apartment/binding, avoiding a second library initializing the GUI thread.
mf._ffi.cdef('''
typedef struct DTRoutingPolicy DTRoutingPolicy;
typedef struct {
    void *QueryInterface; void *AddRef;
    ULONG (__stdcall *Release)(DTRoutingPolicy *);
    void *format_and_property_methods[10];
    HRESULT (__stdcall *SetDefaultEndpoint)(DTRoutingPolicy *, const wchar_t *, int);
    void *SetEndpointVisibility;
} DTRoutingPolicyVtbl;
struct DTRoutingPolicy { DTRoutingPolicyVtbl *lpVtbl; };
''')

def default_output(role=E_CONSOLE):
    with mf._DeviceEnumerator() as enumerator:
        device=mf._ffi.new('IMMDevice **');identifier=mf._ffi.new('LPWSTR *')
        try:
            mf._com.check_error(enumerator._ptr[0][0].lpVtbl.GetDefaultAudioEndpoint(enumerator._ptr[0],0,role,device))
            mf._com.check_error(device[0][0].lpVtbl.GetId(device[0],identifier))
            return mf._ffi.string(identifier[0])
        finally:
            if identifier[0]!=mf._ffi.NULL:mf._ole32.CoTaskMemFree(identifier[0])
            if device[0]!=mf._ffi.NULL:mf._com.release(device)

def _set_default(device_id,role):
    policy=mf._ffi.new('DTRoutingPolicy **')
    mf._com.check_error(mf._ole32.CoCreateInstance(mf._guidof(CLSID_POLICY_CONFIG),mf._ffi.NULL,CLSCTX_ALL,
                         mf._guidof(IID_POLICY_CONFIG),mf._ffi.cast('void **',policy)))
    try:
        mf._com.check_error(policy[0].lpVtbl.SetDefaultEndpoint(policy[0],mf._ffi.new('wchar_t[]',device_id),role))
    finally:policy[0].lpVtbl.Release(policy[0])

def sync_main_output(device_id):
    if not device_id:raise ValueError('请先选择主音频。')
    from audio_engine import devices
    device=next((d for d in devices() if d['id']==device_id),None)
    if device is None:raise ValueError('主音频设备未连接。')
    if not device['supported']:raise ValueError('主音频：'+device['reason'])
    before={role:default_output(role) for role in PLAYBACK_ROLES}
    changed=[]
    try:
        for role in PLAYBACK_ROLES:
            if before[role]!=device_id:
                _set_default(device_id,role);changed.append(role)
        if any(default_output(role)!=device_id for role in PLAYBACK_ROLES):
            raise RuntimeError('Windows 默认输出未切换成功。')
    except (RuntimeError,OSError) as exc:
        # A two-role system mutation is a transaction: restore the first role
        # if the second fails, and expose any rollback failure to the caller.
        errors=[]
        for role in reversed(changed):
            try:_set_default(before[role],role)
            except (RuntimeError,OSError) as error:errors.append(str(error))
        detail=('；恢复原输出失败：'+'；'.join(errors)) if errors else ''
        raise RuntimeError('切换 Windows 默认输出失败：'+str(exc)+detail) from exc
    return dict(device_id=device_id,changed=bool(changed),roles=['console','multimedia'])

def prepare_auxiliary_switch(engine,current,updated):
    """Validate before stopping; only the forwarding worker is restarted.

    Returns whether the caller should resume after committing the settings.
    Never changes Windows defaults or falls back to an unrelated endpoint.
    """
    if not engine.active:return False
    if updated['source_id']!=current['source_id']:raise ValueError('切换主音频前请先停止补声。')
    if updated['target_id']==current['target_id']:return False
    from audio_engine import devices
    row=next((d for d in devices() if d['id']==updated['target_id']),None)
    if row is None:raise ValueError('副音频设备未连接，请连接后刷新设备列表。')
    if not row['supported']:raise ValueError('副音频：'+row['reason'])
    if not engine.stop():raise RuntimeError('副路仍在停止，请稍后切换。')
    return True
