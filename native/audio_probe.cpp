#define NOMINMAX
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <wrl/client.h>
#include <iostream>
#include <iomanip>
#include <string>
using Microsoft::WRL::ComPtr;
void check(HRESULT hr) { if (FAILED(hr)) { std::cerr<<"HRESULT 0x"<<std::hex<<static_cast<unsigned long>(hr)<<"\n"; throw hr; } }
int wmain(int argc,wchar_t** argv) {
    if(argc<2)return 2;
    check(CoInitializeEx(nullptr,COINIT_MULTITHREADED));
    try {
        ComPtr<IMMDeviceEnumerator> enumerator;ComPtr<IMMDevice> device;ComPtr<IAudioClient> audio;
        check(CoCreateInstance(__uuidof(MMDeviceEnumerator),nullptr,CLSCTX_ALL,IID_PPV_ARGS(&enumerator)));
        check(enumerator->GetDevice(argv[1],&device));check(device->Activate(__uuidof(IAudioClient),CLSCTX_ALL,nullptr,&audio));
        REFERENCE_TIME def=0,min=0;check(audio->GetDevicePeriod(&def,&min));
        WAVEFORMATEX* mix=nullptr;check(audio->GetMixFormat(&mix));
        std::cout<<"{\"default_period_ms\":"<<def/10000.<<",\"minimum_period_ms\":"<<min/10000.<<",\"mix_rate\":"<<mix->nSamplesPerSec;
        std::cout<<",\"exclusive_mix_hr\":"<<audio->IsFormatSupported(AUDCLNT_SHAREMODE_EXCLUSIVE,mix,nullptr);
        WAVEFORMATEX pcm={WAVE_FORMAT_PCM,2,48000,192000,4,16,0};
        std::cout<<",\"exclusive_pcm16_hr\":"<<audio->IsFormatSupported(AUDCLNT_SHAREMODE_EXCLUSIVE,&pcm,nullptr);
        // Capability query only: do not initialize a stream or change the engine period.
        ComPtr<IAudioClient3> audio3;
        HRESULT query3=audio.As(&audio3);
        std::cout<<",\"audio_client3_hr\":"<<query3;
        if(SUCCEEDED(query3)) {
            UINT32 normal=0,fundamental=0,minimum=0,maximum=0;
            HRESULT periods=audio3->GetSharedModeEnginePeriod(mix,&normal,&fundamental,&minimum,&maximum);
            std::cout<<",\"shared_period_query_hr\":"<<periods;
            if(SUCCEEDED(periods)) {
                std::cout<<",\"shared_default_ms\":"<<1000.*normal/mix->nSamplesPerSec;
                std::cout<<",\"shared_minimum_ms\":"<<1000.*minimum/mix->nSamplesPerSec;
                std::cout<<",\"shared_fundamental_frames\":"<<fundamental;
                std::cout<<",\"shared_maximum_ms\":"<<1000.*maximum/mix->nSamplesPerSec;
            }
        }
        if(argc>2 && std::wstring(argv[2])==L"--exclusive-init") {
            HRESULT hr=audio->Initialize(AUDCLNT_SHAREMODE_EXCLUSIVE,0,min,min,&pcm,nullptr);
            std::cout<<",\"initialize_hr\":"<<hr;
            if(SUCCEEDED(hr)) { UINT32 frames;REFERENCE_TIME latency;check(audio->GetBufferSize(&frames));check(audio->GetStreamLatency(&latency));std::cout<<",\"exclusive_buffer_frames\":"<<frames<<",\"reported_latency_ms\":"<<latency/10000.; }
        }
        std::cout<<"}\n";CoTaskMemFree(mix);
    } catch(HRESULT) { CoUninitialize();return 1; }
    CoUninitialize();return 0;
}
