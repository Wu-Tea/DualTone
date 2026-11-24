#include "core.hpp"
#include <algorithm>
#include <cmath>
#include <sstream>
namespace dt {
std::string utf8(std::wstring_view s) {
    if (s.empty())
        return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), nullptr, 0, nullptr, nullptr);
    std::string r(n, 0);
    WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), r.data(), n, nullptr, nullptr);
    return r;
}
std::wstring wide(std::string_view s) {
    if (s.empty())
        return {};
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), int(s.size()), nullptr, 0);
    if (!n)
        throw std::runtime_error("文本不是有效 UTF-8");
    std::wstring r(n, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), r.data(), n);
    return r;
}
void check(HRESULT hr) {
    if (FAILED(hr)) {
        std::ostringstream s;
        s << "Windows 音频错误 0x" << std::hex << uint32_t(hr);
        throw std::runtime_error(s.str());
    }
}
double clock_seconds() {
    LARGE_INTEGER t, f;
    QueryPerformanceCounter(&t);
    QueryPerformanceFrequency(&f);
    return double(t.QuadPart) / f.QuadPart;
}
fs::path executable_dir() {
    std::wstring p(32768, 0);
    p.resize(GetModuleFileNameW(nullptr, p.data(), DWORD(p.size())));
    return fs::path(p).parent_path();
}
json defaults() {
    return {{"source_id", ""},
            {"target_id", ""},
            {"input_id", ""},
            {"routing_mode", "direct"},
            {"main_delay_ms", 0.0},
            {"gain", 8.0},
            {"eq_enabled", true},
            {"gains", std::vector<double>(10, 0)},
            {"band_enabled", true},
            {"low", 700.0},
            {"high", 3500.0},
            {"bands",
             json::array({{{"low", 700.0}, {"high", 3500.0}, {"gain_db", 0.0}, {"enabled", true}}})},
            {"spatial_mode", "space"},
            {"spatial_strength", 60.0},
            {"effect_mode", "space"},
            {"reverb_size", 40.0},
            {"reverb_decay", Reverb::DefaultTailSeconds},
            {"reverb_brightness", 40.0}};
}
static void number(const json &j, double lo, double hi, const char *name) {
    if (!j.is_number() || !std::isfinite(j.get<double>()) || j.get<double>() < lo ||
        j.get<double>() > hi)
        throw std::runtime_error(std::string(name) + " 超出允许范围");
}
json validate(json v) {
    if (!v.is_object())
        throw std::runtime_error("配置必须是 JSON 对象");
    json d = defaults();
    for (auto &[k, x] : v.items())
        if (!d.contains(k))
            throw std::runtime_error("配置包含不支持的设置：" + k);
    if (v.value("spatial_mode", std::string{}) == "original") {
        v["spatial_mode"] = "space";
        v["spatial_strength"] = 0.0;
    }
    if (!v.contains("bands") || v["bands"].is_null())
        v["bands"] = json::array({{{"low", v.value("low", 700.0)},
                                   {"high", v.value("high", 3500.0)},
                                   {"gain_db", 0.0},
                                   {"enabled", true}}});
    d.update(v);
    for (auto key : {"source_id", "target_id", "input_id"})
        if (!d[key].is_string() || wide(d[key].get<std::string>()).size() > 256)
            throw std::runtime_error("设备标识无效");
    for (auto key : {"eq_enabled", "band_enabled"})
        if (!d[key].is_boolean())
            throw std::runtime_error("开关值必须为布尔值");
    if (d["spatial_mode"] != "space")
        throw std::runtime_error("副路使用 space 空间补充");
    if (d["routing_mode"] != "direct" && d["routing_mode"] != "sync")
        throw std::runtime_error("routing_mode 必须为 direct 或 sync");
    number(d["main_delay_ms"], 0, MaxMainDelayMs, "main_delay_ms");
    if (d["routing_mode"] == "sync" && d["input_id"] != "" &&
        (d["input_id"] == d["source_id"] || d["input_id"] == d["target_id"]))
        throw std::runtime_error("虚拟入口不能与主音频或副音频相同");
    number(d["gain"], 0, 100, "gain");
    number(d["spatial_strength"], 0, 100, "spatial_strength");
    if (d["effect_mode"] != "space" && d["effect_mode"] != "reverb")
        throw std::runtime_error("effect_mode 必须为 space 或 reverb");
    number(d["reverb_size"], 0, 100, "reverb_size");
    number(d["reverb_decay"], Reverb::MinTailSeconds, Reverb::MaxTailSeconds, "reverb_decay");
    number(d["reverb_brightness"], 0, 100, "reverb_brightness");
    if (!d["gains"].is_array() || d["gains"].size() != EqCount)
        throw std::runtime_error("EQ 需要 10 个频段");
    for (auto &x : d["gains"])
        number(x, -EqLimitDb, EqLimitDb, "EQ");
    auto &bands = d["bands"];
    if (!bands.is_array() || bands.empty() || bands.size() > MaxBands)
        throw std::runtime_error("频段数量必须为 1–8");
    for (auto &b : bands) {
        if (!b.is_object())
            throw std::runtime_error("频段配置字段无效");
        for (auto &[k, x] : b.items())
            if (k != "low" && k != "high" && k != "gain_db" && k != "enabled")
                throw std::runtime_error("频段配置字段无效");
        if (!b.contains("gain_db"))
            b["gain_db"] = 0.;
        if (!b.contains("enabled"))
            b["enabled"] = true;
        number(b.at("low"), 50, 15000, "频段下限");
        number(b.at("high"), 100, 16000, "频段上限");
        number(b["gain_db"], -24, 12, "频段增益");
        if (!b["enabled"].is_boolean() || b["low"].get<double>() >= b["high"].get<double>())
            throw std::runtime_error("频段下限必须小于上限，开关必须为布尔值");
    }
    d["low"] = bands[0]["low"];
    d["high"] = bands[0]["high"];
    return d;
}
json merge(const json &current, json patch) {
    if (!patch.is_object())
        throw std::runtime_error("设置补丁必须是对象");
    if (!patch.contains("bands") && (patch.contains("low") || patch.contains("high"))) {
        auto b = current["bands"];
        for (auto k : {"low", "high"})
            if (patch.contains(k))
                b[0][k] = patch[k];
        patch["bands"] = b;
    }
    json result = current;
    result.update(patch);
    return validate(result);
}
json read_json(const fs::path &p) {
    if (fs::file_size(p) > MaxConfigBytes)
        throw std::runtime_error("配置文件超过 128 KB");
    std::ifstream s(p);
    return json::parse(s);
}
void save_json(const fs::path &p, const json &v) {
    if (!p.parent_path().empty())
        fs::create_directories(p.parent_path());
    auto tmp = p;
    tmp += L".tmp";
    {
        std::ofstream s(tmp, std::ios::binary | std::ios::trunc);
        s << v.dump(2);
        s.flush();
        if (!s)
            throw std::runtime_error("保存配置失败");
    }
    if (!MoveFileExW(tmp.c_str(), p.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        throw std::runtime_error("提交配置文件失败");
}
Store::Store(fs::path dir) : directory(fs::absolute(dir).lexically_normal()) {
    auto p = directory / L"settings.json";
    if (!fs::exists(p))
        return;
    try {
        auto doc = read_json(p);
        int version = doc.at("version");
        if (version < 1 || version > ConfigVersion)
            throw std::runtime_error("不支持的配置版本");
        migrate = version < ConfigVersion ? version : 0;
        auto c = validate(doc.at("current"));
        auto ps = doc.value("presets", json::object());
        if (!ps.is_object() || ps.size() > MaxPresets)
            throw std::runtime_error("预设列表无效");
        for (auto &[name, cfg] : ps.items()) {
            if (name.empty() || wide(name).size() > MaxNameLength)
                throw std::runtime_error("预设名称无效");
            cfg = validate(cfg);
        }
        current = c;
        presets = ps;
    } catch (const std::exception &e) {
        failed = true;
        warning = std::string("旧配置无法读取，原文件保留：") + e.what();
    }
}
void Store::save() {
    if (failed)
        throw std::runtime_error(warning);
    auto p = directory / L"settings.json";
    auto backup = directory / (L"settings.v" + std::to_wstring(migrate) + L".backup.json");
    if (migrate && fs::exists(p) && !fs::exists(backup))
        fs::copy_file(p, backup);
    save_json(p, {{"version", ConfigVersion}, {"current", current}, {"presets", presets}});
    migrate = false;
}
json Store::add(std::string n) {
    auto start = n.find_first_not_of(" \t\r\n"), end = n.find_last_not_of(" \t\r\n");
    if (start == std::string::npos)
        throw std::runtime_error("请输入预设名称");
    n = n.substr(start, end - start + 1);
    if (wide(n).size() > MaxNameLength || presets.size() >= MaxPresets)
        throw std::runtime_error("预设数量或名称长度超过上限");
    if (presets.contains(n))
        throw std::runtime_error("预设名称已存在");
    auto old = presets;
    presets[n] = current;
    try {
        save();
    } catch (...) {
        presets = old;
        throw;
    }
    return {{"name", n}, {"settings", current}};
}
json Store::remove(std::string n) {
    if (!presets.contains(n))
        throw std::runtime_error("预设不存在");
    auto old = presets;
    presets.erase(n);
    try {
        save();
    } catch (...) {
        presets = old;
        throw;
    }
    return {{"deleted", n}};
}
} // namespace dt
