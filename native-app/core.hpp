#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include "vendor/json.hpp"
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
                     ConfigVersion = 2;
inline constexpr size_t MaxConfigBytes = 128 * 1024, MaxPresets = 100, MaxNameLength = 60;
inline constexpr double EqLimitDb = 12, MidCutDb = 12, HeadroomDb = 1, EqQ = 1.4;
inline constexpr int SpatialRampFrames = 480, IdleWaitMs = 100, ControlTimeoutMs = 5000,
                     AnalysisFrames = 4096;
inline constexpr std::array<int, 10> EqFrequencies = {32,   64,   125,  250,  500,
                                                      1000, 2000, 4000, 8000, 16000};
inline constexpr std::array<int, 6> DeviceRates = {44100, 48000, 88200, 96000, 176400, 192000};
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
    bool failed = false, migrate = false;
    explicit Store(fs::path dir);
    void save();
    json add(std::string name);
    json remove(std::string name);
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
struct Processor {
    std::shared_ptr<Dsp> current;
    Sections eq;
    std::vector<std::pair<Sections, double>> bands;
    double mid = 1, target_mid = 1, mid_step = 0;
    int ramp = 0;
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
};
struct Host {
    Store store;
    Engine engine;
    std::recursive_mutex mutex;
    std::atomic_bool quitting = false;
    uint64_t revision = 0;
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
