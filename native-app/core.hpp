#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "vendor/json.hpp"
#include "device_rates.hpp"
#include <array>
#include <atomic>
#include <complex>
#include <deque>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <numbers>
#include <optional>
#include <thread>
#include <vector>
#include <windows.h>
#include <wrl/client.h>
namespace dt {
using json = nlohmann::json;
namespace fs = std::filesystem;
using Microsoft::WRL::ComPtr;
using Complex = std::complex<double>;
inline constexpr int ProcessingRate = 48000, ChannelCount = 2, EqCount = 10, MaxBands = 8,
                     ConfigVersion = 4;
// Sync latency is separate from effect timing. Units are milliseconds unless named otherwise.
inline constexpr double MaxMainDelayMs = 1000, SyncQueueMs = 20, SyncQueueLimitMs = 250,
                        SyncMaxClockCorrection = .002, SyncClockTimeSeconds = 1;
inline constexpr int SyncPacketMs = 10, DelayTransitionFrames = 480;
inline constexpr std::array<const char *, 5> RoutingKeys = {
    "source_id", "target_id", "input_id", "routing_mode", "main_delay_ms"};
struct MainDelay {
    std::vector<std::array<double, 2>> ring;
    size_t position = 0;
    double delay = 0, previous = 0, requested = 0;
    int transition = 0;
    explicit MainDelay(double ms);
    void process(std::vector<double> &samples, double ms);
};
// Per-endpoint clock adaptation; bounded queue, explicit underrun recovery.
struct ClockQueue {
    std::deque<std::array<double, 2>> frames;
    int rate, underruns = 0;
    bool primed = false;
    double position = 0, correction = 0, error = 0;
    explicit ClockQueue(int r) : rate(r) {}
    void push(const std::vector<double> &samples);
    std::vector<double> pull(size_t count);
    double milliseconds() const { return frames.size() * 1000. / rate; }
};
inline constexpr size_t MaxConfigBytes = 128 * 1024, MaxPresets = 100, MaxNameLength = 60;
inline constexpr double EqLimitDb = 12, MidCutDb = 12, HeadroomDb = 1, EqQ = 1.4;
inline constexpr int SpatialRampFrames = 480, IdleWaitMs = 100, ControlTimeoutMs = 5000,
                     AnalysisFrames = 4096;
inline constexpr std::array<int, 10> EqFrequencies = {32,   64,   125,  250,  500,
                                                      1000, 2000, 4000, 8000, 16000};
std::string utf8(std::wstring_view s);
std::wstring wide(std::string_view s);
void check(HRESULT hr);
double clock_seconds();
fs::path executable_dir();
json defaults();
json validate(json value);
json merge(const json &current, json patch);
json read_json(const fs::path &path);
void save_json(const fs::path &path, const json &value);
struct Store {
    fs::path directory;
    json current = defaults(), presets = json::object();
    std::string warning;
    bool failed = false;
    int migrate = 0;
    explicit Store(fs::path dir);
    void save();
    json add(std::string name);
    json remove(std::string name);
    json replace(std::string name);
    json rename(std::string name, std::string replacement);
};
struct Biquad {
    double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0;
    std::array<double, 2> z1{}, z2{};
    double tick(double v, int ch);
    Complex response(double hz) const;
};
using Sections = std::vector<Biquad>;
Sections make_eq(const json &gains);
Sections make_band(double low, double high);
Complex response(const Sections &, double hz);
struct Dsp {
    json cfg;
    Sections eq;
    std::vector<std::pair<Sections, double>> bands;
    double preamp_db = -1;
    explicit Dsp(json settings);
    Complex eq_response(double hz) const;
    Complex band_response(double hz) const;
};
// Eight orthogonally mixed delay lines: wet signal only, never the main route.
struct Reverb {
    static constexpr size_t Lines = 8;
    static constexpr double MinSizeScale = .65, MaxSizeScale = 1.5;
    static constexpr double MinTailSeconds = .2, MaxTailSeconds = 4., DefaultTailSeconds = 1.2;
    static constexpr double MinBrightnessHz = 1200, MaxBrightnessHz = 9000, HighPassHz = 180;
    static constexpr double ParameterSmoothingSeconds = .03, TailFlushMultiples = 2;
    static constexpr int TailPacketMs = 10;
    // Unequal, pairwise-coprime delays at 48 kHz spread reflections in time.
    static constexpr std::array<int, Lines> BaseFrames = {1423, 1783, 1973, 2089, 2269, 2549, 2843, 2969};
    std::array<std::vector<double>, Lines> buffers;
    std::array<size_t, Lines> positions{};
    std::array<double, Lines> delays{}, target_delays{}, feedback{}, target_feedback{}, lowpass{};
    std::array<double, 2> hp_input{}, hp_output{};
    double damping = 0, target_damping = 0;
    int remaining = 0, flush_frames = 0;
    Reverb();
    void configure(const json &cfg, bool reset);
    std::array<double, 2> tick(double left, double right);
};
struct Processor {
    std::shared_ptr<Dsp> current;
    Sections eq;
    std::vector<std::pair<Sections, double>> bands;
    double mid = 1, target_mid = 1, mid_step = 0;
    int ramp = 0;
    std::unique_ptr<Reverb> reverb;
    double wet_mix = 0, wet_target = 0, wet_step = 0;
    int wet_ramp = 0;
    void update(std::shared_ptr<Dsp> dsp);
    void process(std::vector<double> &interleaved, bool paused);
};
struct Resampler {
    int up = 1, down = 1;
    const double *taps = nullptr;
    size_t taps_size = 0;
    int64_t inputs = 0, outputs = 0, origin = 0;
    std::vector<double> history;
    Resampler(int source, int target);
    std::vector<double> process(const std::vector<double> &samples);
};
void fft(std::vector<Complex> &values, bool inverse = false);
json devices();
std::string default_output(int role = 0);
void sync_main(const std::string &id);
json effects_report(const json &cfg);
json measure_latency(const json &cfg, bool probe);
struct Engine {
    std::atomic_bool active = false, stop_flag = false, paused = false, analysis = false;
    std::thread worker;
    std::mutex mutex;
    json telemetry;
    std::atomic<std::shared_ptr<Dsp>> dsp;
    std::deque<std::array<double, 4>> samples;
    Engine();
    ~Engine();
    void start(std::shared_ptr<Dsp> value);
    void stop();
    void update(std::shared_ptr<Dsp> value);
    json status();
    std::vector<std::array<double, 4>> spectrum_samples();
    void run();
    void run_sync();
};
struct Host {
    Store store;
    Engine engine;
    std::recursive_mutex mutex;
    std::atomic_bool quitting = false;
    uint64_t revision = 0;
    json appearance = {{"theme", "dark"}};
    explicit Host(fs::path dir);
    json command(const std::string &name, const json &args = json::object());
    json set(json patch);
    json schema();
};
std::wstring pipe_name(const fs::path &dir);
std::optional<json> request(const fs::path &dir, const json &message);
struct Server {
    Host &host;
    std::thread worker;
    std::atomic_bool stop_flag = false;
    HANDLE first = INVALID_HANDLE_VALUE;
    explicit Server(Host &);
    ~Server();
    void run();
};
int cli_main(int argc, wchar_t **argv);
json envelope(Host &, const json &message);
} // namespace dt
