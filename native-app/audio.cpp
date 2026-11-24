#include "core.hpp"
#include <algorithm>
#include <audioclient.h>
#include <avrt.h>
#include <endpointvolume.h>
#include <mmdeviceapi.h>
// Windows property-key declarations require the device API definitions first.
#include <functiondiscoverykeys_devpkey.h>
namespace dt {
static constexpr PROPERTYKEY EndpointFormFactor = {
    {0x1da5d803, 0xd492, 0x4edd, {0x8c, 0x23, 0xe0, 0xc0, 0xff, 0xee, 0x7f, 0x0e}}, 0};
struct ComScope {
    HRESULT result = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    ComScope() {
        if (FAILED(result) && result != RPC_E_CHANGED_MODE)
            check(result);
    }
    ~ComScope() {
        if (SUCCEEDED(result))
            CoUninitialize();
    }
};
static ComPtr<IMMDeviceEnumerator> enumerator() {
    ComPtr<IMMDeviceEnumerator> e;
    check(CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, IID_PPV_ARGS(&e)));
    return e;
}
static ComPtr<IMMDevice> endpoint(const std::string &id) {
    ComPtr<IMMDevice> d;
    check(enumerator()->GetDevice(wide(id).c_str(), &d));
    return d;
}
static std::string identifier(IMMDevice *d) {
    LPWSTR p = nullptr;
    check(d->GetId(&p));
    auto id = utf8(p);
    CoTaskMemFree(p);
    return id;
}
static ComPtr<IAudioClient> client(IMMDevice *d) {
    ComPtr<IAudioClient> a;
    check(d->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, &a));
    return a;
}
static bool floating(WAVEFORMATEX *f) {
    return f->wBitsPerSample == 32 &&
           (f->wFormatTag == WAVE_FORMAT_IEEE_FLOAT ||
            (f->wFormatTag == WAVE_FORMAT_EXTENSIBLE &&
             reinterpret_cast<WAVEFORMATEXTENSIBLE *>(f)->SubFormat == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT));
}
static std::string reason(WAVEFORMATEX *f) {
    if (!floating(f))
        return "当前混音格式不是 float32";
    if (f->nChannels != ChannelCount)
        return "需要立体声输出";
    if (std::find(DeviceRates.begin(), DeviceRates.end(), int(f->nSamplesPerSec)) == DeviceRates.end())
        return "不支持的设备采样率";
    return {};
}
json devices() {
    ComScope com;
    auto e = enumerator();
    ComPtr<IMMDeviceCollection> list;
    check(e->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &list));
    UINT count;
    check(list->GetCount(&count));
    json result = json::array();
    for (UINT i = 0; i < count; i++) {
        ComPtr<IMMDevice> d;
        check(list->Item(i, &d));
        json r = {{"id", identifier(d.Get())},
                  {"name", "音频设备"},
                  {"icon", "wave"},
                  {"supported", false},
                  {"reason", "无法读取格式"}};
        try {
            ComPtr<IPropertyStore> store;
            check(d->OpenPropertyStore(STGM_READ, &store));
            PROPVARIANT value;
            PropVariantInit(&value);
            if (SUCCEEDED(store->GetValue(PKEY_Device_FriendlyName, &value)) && value.vt == VT_LPWSTR)
                r["name"] = utf8(value.pwszVal);
            PropVariantClear(&value);
            if (SUCCEEDED(store->GetValue(EndpointFormFactor, &value)) && value.vt == VT_UI4) {
                auto f = value.ulVal;
                r["icon"] = (f == 1             ? "speaker"
                             : f == 2           ? "line"
                             : f == 3 || f == 5 ? "headphones"
                             : f == 7 || f == 8 ? "digital"
                             : f == 9           ? "monitor"
                                                : "wave");
            }
            PropVariantClear(&value);
            auto a = client(d.Get());
            WAVEFORMATEX *f = nullptr;
            check(a->GetMixFormat(&f));
            r["rate"] = f->nSamplesPerSec;
            r["channels"] = f->nChannels;
            r["float32"] = floating(f);
            r["reason"] = reason(f);
            r["supported"] = reason(f).empty();
            CoTaskMemFree(f);
        } catch (const std::exception &ex) {
            r["reason"] = ex.what();
        }
        result.push_back(r);
    }
    return result;
}
std::string default_output(int role) {
    ComScope com;
    ComPtr<IMMDevice> d;
    check(enumerator()->GetDefaultAudioEndpoint(eRender, ERole(role), &d));
    return identifier(d.Get());
}
// Windows PolicyConfig COM ABI; only render defaults for console and multimedia.
struct PolicyVtbl {
    void *QueryInterface;
    void *AddRef;
    ULONG(__stdcall *Release)(void *);
    void *methods[10];
    HRESULT(__stdcall *SetDefaultEndpoint)(void *, LPCWSTR, ERole);
    void *visibility;
};
struct Policy {
    PolicyVtbl *vtbl;
};
static void set_default(const std::string &id, int role) {
    CLSID cls;
    IID iid;
    CLSIDFromString(L"{870af99c-171d-4f9e-af0d-e63df40c2bc9}", &cls);
    IIDFromString(L"{f8679f50-850a-41cf-9c72-430f290290c8}", &iid);
    Policy *p = nullptr;
    check(CoCreateInstance(cls, nullptr, CLSCTX_ALL, iid, reinterpret_cast<void **>(&p)));
    auto hr = p->vtbl->SetDefaultEndpoint(p, wide(id).c_str(), ERole(role));
    p->vtbl->Release(p);
    check(hr);
}
void sync_main(const std::string &id) {
    ComScope com;
    auto d = endpoint(id);
    auto a = client(d.Get());
    WAVEFORMATEX *f = nullptr;
    check(a->GetMixFormat(&f));
    auto why = reason(f);
    CoTaskMemFree(f);
    if (!why.empty())
        throw std::runtime_error(why);
    auto c = default_output(0), m = default_output(1);
    bool changed = false;
    try {
        if (c != id) {
            set_default(id, 0);
            changed = true;
        }
        if (m != id)
            set_default(id, 1);
    } catch (...) {
        if (changed)
            set_default(c, 0);
        throw;
    }
}
struct Stream {
    ComPtr<IAudioClient> audio;
    ComPtr<IAudioRenderClient> render;
    ComPtr<IAudioCaptureClient> capture;
    HANDLE ready = nullptr;
    UINT capacity = 0, rate = 0;
    bool started = false;
    int discontinuities = 0;
    bool first = true;
    struct Packet {
        std::vector<double> data;
        double timestamp = 0, received = 0;
        UINT64 position = 0;
        DWORD flags = 0;
    };
    Stream(const std::string &id, bool loopback) {
        auto d = endpoint(id);
        audio = client(d.Get());
        WAVEFORMATEX *fmt = nullptr;
        check(audio->GetMixFormat(&fmt));
        auto why = reason(fmt);
        rate = fmt->nSamplesPerSec;
        if (!why.empty()) {
            CoTaskMemFree(fmt);
            throw std::runtime_error(why);
        }
        auto hr = audio->Initialize(AUDCLNT_SHAREMODE_SHARED,
                                    AUDCLNT_STREAMFLAGS_NOPERSIST | AUDCLNT_STREAMFLAGS_EVENTCALLBACK |
                                        (loopback ? AUDCLNT_STREAMFLAGS_LOOPBACK : 0),
                                    0, 0, fmt, nullptr);
        CoTaskMemFree(fmt);
        check(hr);
        ready = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        if (!ready)
            throw std::runtime_error("无法创建音频事件");
        check(audio->SetEventHandle(ready));
        check(audio->GetBufferSize(&capacity));
        if (loopback)
            check(audio->GetService(IID_PPV_ARGS(&capture)));
        else
            check(audio->GetService(IID_PPV_ARGS(&render)));
    }
    ~Stream() {
        if (started)
            audio->Stop();
        if (ready)
            CloseHandle(ready);
    }
    void start() {
        check(audio->Start());
        started = true;
    }
    UINT padding() {
        UINT p;
        check(audio->GetCurrentPadding(&p));
        return p;
    }
    std::optional<Packet> read() {
        UINT available;
        check(capture->GetNextPacketSize(&available));
        if (!available)
            return {};
        BYTE *data;
        UINT frames;
        Packet p;
        UINT64 stamp;
        check(capture->GetBuffer(&data, &frames, &p.flags, &p.position, &stamp));
        p.timestamp = stamp / 1e7;
        p.received = clock_seconds();
        p.data.resize(frames * 2);
        if (!(p.flags & AUDCLNT_BUFFERFLAGS_SILENT) && data)
            for (size_t i = 0; i < p.data.size(); i++)
                p.data[i] = reinterpret_cast<float *>(data)[i];
        if (!first && (p.flags & AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY))
            discontinuities++;
        first = false;
        check(capture->ReleaseBuffer(frames));
        return p;
    }
    void play(const std::vector<double> &p, std::atomic_bool &stop) {
        size_t pos = 0;
        while (pos < p.size() / 2 && !stop) {
            auto count = std::min<size_t>(capacity - padding(), p.size() / 2 - pos);
            if (!count) {
                WaitForSingleObject(ready, IdleWaitMs);
                continue;
            }
            BYTE *data = nullptr;
            check(render->GetBuffer(UINT(count), &data));
            for (size_t i = 0; i < count * 2; i++)
                reinterpret_cast<float *>(data)[i] = float(p[pos * 2 + i]);
            check(render->ReleaseBuffer(UINT(count), 0));
            pos += count;
        }
    }
};
Engine::Engine() {
    telemetry = {{"state", "stopped"}, {"message", "准备就绪"}, {"queue_ms", 0.0},
                 {"blocks", 0},        {"uptime", 0.0},         {"input_peak", 0.0},
                 {"output_peak", 0.0}, {"discontinuities", 0}};
}
Engine::~Engine() {
    stop();
}
void Engine::update(std::shared_ptr<Dsp> v) {
    dsp.store(v);
}
json Engine::status() {
    std::lock_guard l(mutex);
    return telemetry;
}
std::vector<std::array<double, 4>> Engine::spectrum_samples() {
    std::lock_guard l(mutex);
    return {samples.begin(), samples.end()};
}
void Engine::start(std::shared_ptr<Dsp> v) {
    if (v->cfg["routing_mode"] != "direct")
        throw std::runtime_error("虚拟声卡双路同步已撤回，请使用主音频直出");
    if (active)
        throw std::runtime_error("音频正在运行");
    stop();
    if (v->cfg["source_id"] == v->cfg["target_id"] || v->cfg["target_id"] == "" ||
        v->cfg["source_id"] == "")
        throw std::runtime_error("请选择两个不同的音频设备");
    if (v->cfg["routing_mode"] == "sync" &&
        (v->cfg["input_id"] == "" || v->cfg["input_id"] == v->cfg["source_id"] ||
         v->cfg["input_id"] == v->cfg["target_id"]))
        throw std::runtime_error("请选择独立的虚拟音频入口");
    update(v);
    stop_flag = false;
    active = true;
    {
        std::lock_guard l(mutex);
        samples.clear();
        telemetry = {{"state", "starting"}, {"message", "正在连接音频设备…"},
                     {"queue_ms", 0.0},     {"blocks", 0},
                     {"uptime", 0.0},       {"input_peak", 0.0},
                     {"output_peak", 0.0},  {"discontinuities", 0}};
    }
    worker = std::thread([this] { run(); });
}
void Engine::stop() {
    stop_flag = true;
    if (worker.joinable())
        worker.join();
    active = false;
}
void Engine::run() {
    HANDLE singleton = nullptr, task = nullptr;
    try {
        ComScope com;
        singleton = CreateMutexW(nullptr, FALSE, L"Local\\CodexDualAudioTrial");
        if (!singleton || GetLastError() == ERROR_ALREADY_EXISTS)
            throw std::runtime_error("已有补声工具正在播放，请先停止旧版");
        DWORD index = 0;
        task = AvSetMmThreadCharacteristicsW(L"Pro Audio", &index);
        auto d = dsp.load();
        if (d->cfg["routing_mode"] == "sync") {
            run_sync();
        } else {
        Stream output(d->cfg["target_id"], false), input(d->cfg["source_id"], true);
        Resampler in(input.rate, ProcessingRate), out(ProcessingRate, output.rate);
        Processor processor;
        processor.update(d);
        output.start();
        input.start();
        double begin = clock_seconds(), last = begin, max_dsp = 0;
        int blocks = 0;
        {
            std::lock_guard l(mutex);
            telemetry.update({{"state", "running"},
                              {"message", "正在补声"},
                              {"source_rate", input.rate},
                              {"target_rate", output.rate},
                              {"processing_rate", ProcessingRate},
                              {"buffer_capacity_ms", output.capacity * 1000. / output.rate},
                              {"wakeup_mode", "WASAPI audio-ready event"},
                              {"scheduler", task ? "Pro Audio" : "normal"}});
        }
        while (!stop_flag) {
            auto packet = input.read();
            bool tail_packet = false;
            if (!packet && processor.reverb && processor.reverb->remaining > 0) {
                // A stopped capture stream still needs a clock for the wet tail.
                // Recheck capture first; never insert silence ahead of a ready packet.
                WaitForSingleObject(input.ready, Reverb::TailPacketMs);
                packet = input.read();
                if (!packet) {
                    if (output.padding() > output.rate * Reverb::TailPacketMs / 1000)
                        continue;
                    packet = Stream::Packet{};
                    packet->data.resize(input.rate * Reverb::TailPacketMs / 1000 * ChannelCount);
                    tail_packet = true;
                }
            }
            if (!packet) {
                if (clock_seconds() - last > .1) {
                    std::lock_guard l(mutex);
                    telemetry["input_peak"] = 0.;
                    telemetry["output_peak"] = 0.;
                }
                WaitForSingleObject(input.ready, IdleWaitMs);
                continue;
            }
            last = clock_seconds();
            double begin_dsp = last, peak = 0;
            for (auto v : packet->data)
                peak = std::max(peak, abs(v));
            auto data = in.process(packet->data);
            auto original = analysis.load() ? data : std::vector<double>{};
            processor.update(dsp.load());
            processor.process(data, paused);
            auto rendered = out.process(data);
            double processed = (clock_seconds() - begin_dsp) * 1000;
            max_dsp = std::max(max_dsp, processed);
            output.play(rendered, stop_flag);
            double op = 0;
            for (auto v : data)
                op = std::max(op, abs(v));
            std::lock_guard l(mutex);
            if (!original.empty()) {
                for (size_t i = 0; i < data.size(); i += 2)
                    samples.push_back({original[i], original[i + 1], data[i], data[i + 1]});
                while (samples.size() > AnalysisFrames)
                    samples.pop_front();
            }
            telemetry.update(
                {{"queue_ms", output.padding() * 1000. / output.rate},
                 {"blocks", ++blocks},
                 {"uptime", clock_seconds() - begin},
                 {"input_peak", peak},
                 {"output_peak", op},
                 {"discontinuities", input.discontinuities},
                 {"reverb_tail", tail_packet},
                 {"dsp_ms", processed},
                 {"dsp_max_ms", max_dsp}});
            if (!tail_packet) {
                telemetry["source_timestamp_valid"] = !(packet->flags & AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR) &&
                                                       abs(packet->timestamp-packet->received)<=1;
                telemetry["source_clock_skew_ms"] = (packet->timestamp-packet->received)*1000;
            }
        }
        {
            std::lock_guard l(mutex);
            telemetry.update({{"state", "stopped"},
                              {"message", "补声已停止"},
                              {"queue_ms", 0.0},
                              {"input_peak", 0.0},
                              {"output_peak", 0.0}});
        }
    }
    } catch (const std::exception &ex) {
        std::lock_guard l(mutex);
        telemetry.update({{"state", "error"},
                          {"message", std::string("补声已停止：") + ex.what()},
                          {"input_peak", 0.0},
                          {"output_peak", 0.0}});
    }
    if (task)
        AvRevertMmThreadCharacteristics(task);
    if (singleton)
        CloseHandle(singleton);
    active = false;
}
// Routing ownership is scoped to playback. Only restore defaults still pointing
// at our ingress; never overwrite a user's subsequent device selection.
void Engine::run_sync() {
    auto initial = dsp.load();
    const auto cfg = initial->cfg;
    const std::string ingress = cfg["input_id"];
    Stream input(ingress, true), main(cfg["source_id"], false), auxiliary(cfg["target_id"], false);
    std::array<std::string, 2> saved{default_output(0), default_output(1)};
    for (auto &id : saved) if (id == ingress) id = cfg["source_id"];
    bool routing_owned = false;
    auto restore = [&] {
        if (!routing_owned) return;
        std::string errors;
        for (int role = 0; role < 2; ++role) {
            try {
                if (default_output(role) == ingress) set_default(saved[role], role);
            } catch (const std::exception &e) { errors += std::string(e.what()) + " "; }
        }
        routing_owned = false;
        if (!errors.empty()) throw std::runtime_error("恢复 Windows 输出失败，请在系统中选择主音箱：" + errors);
    };
    try {
        Resampler incoming(input.rate, ProcessingRate), main_resample(ProcessingRate, main.rate),
                  auxiliary_resample(ProcessingRate, auxiliary.rate);
        ClockQueue main_queue(main.rate), auxiliary_queue(auxiliary.rate);
        MainDelay delay(cfg["main_delay_ms"]);
        Processor processor; processor.update(initial);
        main.start(); auxiliary.start(); input.start();
        // Both outputs are open before switching any application to the ingress.
        routing_owned = true;
        sync_main(ingress);
        double begin = clock_seconds(), last_feed = begin, max_dsp = 0;
        int blocks = 0, synthetic = 0;
        auto feed = [&](std::vector<double> raw, bool silence) {
            auto start = clock_seconds();
            auto current = dsp.load();
            auto data = incoming.process(raw);
            auto original = data;
            double ip = 0, op = 0;
            for (auto x : data) ip = std::max(ip, std::abs(x));
            auto dry = data;
            delay.process(dry, current->cfg["main_delay_ms"]);
            main_queue.push(main_resample.process(dry));
            processor.update(current);
            processor.process(data, paused);
            auxiliary_queue.push(auxiliary_resample.process(data));
            for (auto x : data) op = std::max(op, std::abs(x));
            auto elapsed = (clock_seconds() - start) * 1000;
            max_dsp = std::max(max_dsp, elapsed);
            std::lock_guard lock(mutex);
            if (analysis.load()) {
                for (size_t i = 0; i < data.size(); i += 2)
                    samples.push_back({original[i], original[i + 1], data[i], data[i + 1]});
                while (samples.size() > AnalysisFrames) samples.pop_front();
            }
            telemetry.update({{"blocks", ++blocks}, {"input_peak", ip}, {"output_peak", op},
                              {"dsp_ms", elapsed}, {"dsp_max_ms", max_dsp},
                              {"synthetic_packets", synthetic += silence},
                              {"main_delay_ms", current->cfg["main_delay_ms"]}});
        };
        auto render = [&](Stream &output, ClockQueue &queue) {
            auto count = std::min(output.capacity - output.padding(), output.rate * SyncPacketMs / 1000);
            if (!count) return;
            auto data = queue.pull(count);
            BYTE *buffer = nullptr;
            check(output.render->GetBuffer(count, &buffer));
            for (size_t i = 0; i < data.size(); ++i) reinterpret_cast<float *>(buffer)[i] = float(data[i]);
            check(output.render->ReleaseBuffer(count, 0));
        };
        {
            std::lock_guard lock(mutex);
            telemetry.update({{"state", "running"}, {"message", "双路同步"}, {"routing_mode", "sync"},
                {"source_rate", input.rate}, {"main_rate", main.rate}, {"target_rate", auxiliary.rate},
                {"processing_rate", ProcessingRate}, {"jitter_buffer_ms", SyncQueueMs},
                {"source_timestamp_valid", false}, {"scheduler", "independent event-driven render queues"}});
        }
        HANDLE events[] = {input.ready, main.ready, auxiliary.ready};
        while (!stop_flag) {
            while (auto packet = input.read()) {
                {
                    std::lock_guard lock(mutex);
                    telemetry["capture_packet_ms"] = packet->data.size() * 500. / input.rate;
                }
                feed(std::move(packet->data), false);
                last_feed = clock_seconds();
                if (stop_flag) break;
            }
            // When loopback stops delivering packets, clock silence through the
            // delay line so final main samples and auxiliary reverb can finish.
            while (clock_seconds() - last_feed >= SyncPacketMs / 1000. &&
                std::min(main_queue.milliseconds(), auxiliary_queue.milliseconds()) < SyncQueueMs + SyncPacketMs) {
                feed(std::vector<double>(input.rate * SyncPacketMs / 1000 * ChannelCount), true);
                last_feed += SyncPacketMs / 1000.;
            }
            render(main, main_queue);
            render(auxiliary, auxiliary_queue);
            {
                std::lock_guard lock(mutex);
                telemetry.update({{"uptime", clock_seconds() - begin},
                    {"queue_ms", auxiliary_queue.milliseconds() + auxiliary.padding() * 1000. / auxiliary.rate},
                    {"main_queue_ms", main_queue.milliseconds() + main.padding() * 1000. / main.rate},
                    {"main_clock_ppm", main_queue.correction * 1e6},
                    {"auxiliary_clock_ppm", auxiliary_queue.correction * 1e6},
                    {"main_underruns", main_queue.underruns}, {"auxiliary_underruns", auxiliary_queue.underruns},
                    {"discontinuities", input.discontinuities}});
            }
            WaitForMultipleObjects(3, events, FALSE, SyncPacketMs);
        }
        check(main.audio->Stop()); main.started = false;
        check(auxiliary.audio->Stop()); auxiliary.started = false;
        restore();
        std::lock_guard lock(mutex);
        telemetry.update({{"state", "stopped"}, {"message", "已停止并恢复系统输出"},
                          {"queue_ms", 0.}, {"main_queue_ms", 0.}, {"input_peak", 0.}, {"output_peak", 0.}});
    } catch (const std::exception &e) {
        std::string reason = e.what();
        try { restore(); } catch (const std::exception &r) { reason += std::string("；") + r.what(); }
        throw std::runtime_error(reason);
    }
}
json measure_latency(const json &cfg, bool probe) {
    if (cfg.value("routing_mode", "direct") == "sync")
        throw std::runtime_error("双路同步请使用主路延迟试听调节；旧数字转发测量仅适用于直出模式");
    if (cfg.value("effect_mode", "space") == "reverb")
        throw std::runtime_error("混响包含有意加入的反射与尾音；请切回空间补充后测量转发延迟");
    ComScope com;
    Stream source(cfg["source_id"], true), target(cfg["target_id"], true);
    source.start();
    target.start();
    std::atomic_bool stop = false;
    std::exception_ptr probe_error;
    std::thread generator;
    if (probe)
        generator = std::thread([&] {
            try {
                ComScope c;
                Stream s(cfg["source_id"], false);
                s.start();
                uint32_t seed = 104729;
                while (!stop) {
                    std::vector<double> p(s.rate / 100 * 2);
                    for (size_t i = 0; i < p.size(); i += 2) {
                        seed = 1664525 * seed + 1013904223;
                        p[i] = p[i + 1] = (double(seed) / UINT32_MAX * 2 - 1) * .008;
                    }
                    s.play(p, stop);
                }
            } catch (...) {
                probe_error = std::current_exception();
            }
        });
    std::vector<double> x, y;
    double firstx = 0, firsty = 0, lastx = 0, lasty = 0, gaps[2]{};
    size_t nx = 0, ny = 0;
    bool valid = true;
    try {
        double end = clock_seconds() + 4;
        while (clock_seconds() < end) {
            for (int c = 0; c < 2; c++) {
                auto &s = c ? target : source;
                auto p = s.read();
                if (!p)
                    continue;
                auto &data = c ? y : x;
                auto &first = c ? firsty : firstx;
                auto &last = c ? lasty : lastx;
                auto &n = c ? ny : nx;
                if (data.empty())
                    first = p->timestamp;
                else
                    gaps[c] = std::max(gaps[c], abs(p->timestamp - last - double(n) / s.rate));
                last = p->timestamp;
                n = p->data.size() / 2;
                valid &= !(p->flags & AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR) &&
                         abs(p->timestamp - p->received) <= 1;
                data.insert(data.end(), p->data.begin(), p->data.end());
            }
            Sleep(1);
        }
    } catch (...) {
        stop = true;
        if (generator.joinable())
            generator.join();
        throw;
    }
    stop = true;
    if (generator.joinable())
        generator.join();
    if (probe_error)
        std::rethrow_exception(probe_error);
    if (x.empty() || y.empty())
        throw std::runtime_error("没有足够的音频数据");
    if (!valid)
        throw std::runtime_error("设备时间戳异常，本次不报告延迟");
    Processor dsp;
    dsp.update(std::make_shared<Dsp>(cfg));
    Resampler in(source.rate, ProcessingRate), out(ProcessingRate, target.rate);
    x = in.process(x);
    dsp.process(x, false);
    x = out.process(x);
    double power[2]{};
    for (size_t i = 0; i < y.size(); i++)
        power[i % 2] += y[i] * y[i];
    int channel = power[1] > power[0] ? 1 : 0;
    size_t a = x.size() / 2, b = y.size() / 2, n = 1;
    while (n < a + b)
        n *= 2;
    std::vector<Complex> ax(n), by(n);
    for (size_t i = 0; i < a; i++)
        ax[i] = x[i * 2 + channel];
    for (size_t i = 0; i < b; i++)
        by[i] = y[i * 2 + channel];
    fft(ax);
    fft(by);
    for (size_t i = 0; i < n; i++)
        by[i] *= std::conj(ax[i]);
    fft(by, true);
    double offset = firsty - firstx, best = -1;
    int lag = 0;
    for (int l = -int(a) + 1; l < int(b); l++) {
        if (abs(double(l) / target.rate + offset) >= .2)
            continue;
        auto v = abs(by[l < 0 ? n + l : l].real());
        if (v > best) {
            best = v;
            lag = l;
        }
    }
    double dot = 0, px = 0, py = 0;
    for (int i = std::max(0, -lag); i < int(a) && i + lag < int(b); i++) {
        double u = x[i * 2 + channel], v = y[(i + lag) * 2 + channel];
        dot += u * v;
        px += u * u;
        py += v * v;
    }
    if (px * py < 1e-20)
        throw std::runtime_error("音频过低，无法测量");
    double corr = abs(dot) / sqrt(px * py);
    return {
        {"method", "WASAPI QPC + matched-DSP correlation"},
        {"reliable", corr >= .8 && std::max(gaps[0], gaps[1]) < .002 && !source.discontinuities && !target.discontinuities},
        {"transport_lag_ms", (double(lag) / target.rate + offset) * 1000},
        {"correlation", corr},
        {"discontinuities", {{"source", source.discontinuities}, {"target", target.discontinuities}}},
        {"timestamp_errors", {{"source", 0}, {"target", 0}}},
        {"max_timestamp_gap_ms", {{"source", gaps[0] * 1000}, {"target", gaps[1] * 1000}}},
        {"note", "数字转发估计，不包含参考滤波群延迟和未测量的蓝牙、设备内部、声学延迟。"}};
}
} // namespace dt
