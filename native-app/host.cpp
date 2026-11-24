#include "core.hpp"
#include <algorithm>
#include <bcrypt.h>
#include <regex>
#include <sddl.h>
#include <sstream>
namespace dt {
Host::Host(fs::path dir) : store(dir) {
    engine.update(std::make_shared<Dsp>(store.current));
}
json Host::set(json patch) {
    if (store.failed)
        throw std::runtime_error(store.warning);
    auto cfg = merge(store.current, patch);
    auto compiled = std::make_shared<Dsp>(cfg);
    if (cfg["source_id"] != "" && cfg["source_id"] == cfg["target_id"])
        throw std::runtime_error("主音频和副音频必须不同");
    bool source_changed = cfg["source_id"] != store.current["source_id"],
         target_changed = cfg["target_id"] != store.current["target_id"];
    bool route_changed = cfg["routing_mode"] != store.current["routing_mode"] ||
                         cfg["input_id"] != store.current["input_id"];
    if (engine.active && (source_changed || route_changed ||
                         (target_changed && cfg["routing_mode"] == "sync")))
        throw std::runtime_error("切换音频路由前请先停止播放");
    bool resume = engine.active && target_changed;
    if (resume) {
        auto ds = devices();
        bool found = false;
        for (auto &row : ds)
            if (row["id"] == cfg["target_id"]) {
                found = true;
                if (!row["supported"].get<bool>())
                    throw std::runtime_error(row["reason"]);
            }
        if (!found)
            throw std::runtime_error("副音频设备未连接，请连接后刷新");
        engine.stop();
    }
    if (source_changed && cfg["source_id"] != "" && cfg["routing_mode"] == "direct")
        sync_main(cfg["source_id"]);
    auto old = store.current;
    store.current = cfg;
    try {
        store.save();
    } catch (...) {
        store.current = old;
        throw;
    }
    engine.update(compiled);
    revision++;
    if (resume)
        engine.start(compiled);
    return cfg;
}
json Host::schema() {
    return {{"version", ConfigVersion},
            {"defaults", defaults()},
            {"limits",
             {{"gain", {0, 100}},
              {"main_delay_ms", {0, MaxMainDelayMs}},
              {"low", {50, 15000}},
              {"high", {100, 16000}},
              {"spatial_strength", {0, 100}},
              {"reverb_size", {0, 100}},
              {"reverb_decay", {Reverb::MinTailSeconds, Reverb::MaxTailSeconds}},
              {"reverb_brightness", {0, 100}}}},
            {"effects", {{"modes", {"space", "reverb"}}, {"default", "space"},
                         {"reverb", {{"wet_only", true}, {"size_unit", "percent"},
                         {"decay_unit", "seconds"}, {"brightness_unit", "percent"},
                         {"effect_added_main_delay_frames", 0},
                         {"semantics", "Auxiliary-only FDN tail; decay is nominal low-frequency RT60. EQ and bands filter the reverb input. Spatial strength is retained but inactive in reverb mode."}}}}},
            {"eq_frequencies_hz", EqFrequencies},
            {"eq_gain_range_db", {-12, 12}},
            {"spatial",
             {{"modes", {"space"}},
              {"strength_percent", {0, 100}},
              {"max_mid_cut_db", MidCutDb},
              {"transition_ms", 10},
              {"ui_body_retention_percent", "100 * 10 ** (-max_mid_cut_db * spatial_strength / 100 / 20)"},
              {"legacy_original", "Accepted for old configurations; normalized to space with strength 0 (100% body)."},
              {"added_buffer_frames", 0},
              {"semantics", "Auxiliary Mid attenuation; Side retained. Not voice separation."}}},
            {"filter_bands",
             {{"min_count", 1},
              {"max_count", MaxBands},
              {"gain_db", {-24, 12}},
              {"low_hz", {50, 15000}},
              {"high_hz", {100, 16000}},
              {"semantics", "Parallel weighted bandpasses; low < high. All disabled = silence when band_enabled. Global off = bypass."},
              {"fields", {"low", "high", "gain_db", "enabled"}},
              {"legacy", "low/high edit the first band only."}}},
            {"commands",
             {"devices", "get", "set", "presets", "preset", "preset-add", "preset-delete", "effects",
              "start", "stop", "status", "latency", "pause", "import", "export", "shutdown", "serve",
              "schema"}},
            {"scope", "All DSP settings affect auxiliary output only."},
            {"routing", {{"modes", {"direct", "sync"}}, {"default", "direct"},
                         {"main_device", "source_id"}, {"auxiliary_device", "target_id"},
                         {"virtual_input", "input_id"}, {"delay_unit", "milliseconds"},
                         {"jitter_buffer_ms", SyncQueueMs},
                         {"semantics", "sync: virtual render loopback feeds both outputs; main_delay_ms adds main-only delay. Normal stop/error restores defaults if still owned. Communications unchanged. Effects and pause affect auxiliary only. Presets/import preserve routing."}}}};
}
json Host::command(const std::string &c, const json &args) {
    std::lock_guard lock(mutex);
    if (c == "schema")
        return schema();
    if (c == "devices")
        return devices();
    if (c == "get")
        return store.current;
    if (c == "presets")
        return store.presets;
    if (c == "status")
        return {{"running", true},
                {"audio", engine.status()},
                {"settings", store.current},
                {"paused", engine.paused.load()},
                {"configuration_warning", store.warning}};
    if (c == "set")
        return set(args);
    if (c == "preset-add") {
        auto r = store.add(args.at("name"));
        revision++;
        return r;
    }
    if (c == "preset-delete") {
        auto r = store.remove(args.at("name"));
        revision++;
        return r;
    }
    if (c == "preset") {
        auto name = args.at("name").get<std::string>();
        if (!store.presets.contains(name))
            throw std::runtime_error("预设不存在");
        auto p = store.presets[name];
        for (auto key : RoutingKeys) p[key] = store.current[key];
        return set(p);
    }
    if (c == "effects")
        return effects_report(store.current);
    if (c == "start") {
        if (store.failed)
            throw std::runtime_error(store.warning);
        if (!engine.active) {
            auto cfg = store.current;
            if (cfg["source_id"] == "")
                cfg["source_id"] = default_output();
            if (cfg["target_id"] == "" || cfg["source_id"] == cfg["target_id"])
                throw std::runtime_error("请选择不同的主音频和副音频");
            if (cfg["routing_mode"] == "direct") sync_main(cfg["source_id"]);
            store.current = cfg;
            engine.start(std::make_shared<Dsp>(cfg));
            revision++;
        }
        return engine.status();
    }
    if (c == "stop") {
        engine.stop();
        return engine.status();
    }
    if (c == "pause") {
        if (!args.at("enabled").is_boolean())
            throw std::runtime_error("enabled 必须为布尔值");
        engine.paused = args["enabled"].get<bool>();
        return {{"paused", engine.paused.load()}};
    }
    if (c == "shutdown") {
        quitting = true;
        engine.stop();
        return {{"shutting_down", true}};
    }
    throw std::runtime_error("未知命令：" + c);
}
json envelope(Host &h, const json &msg) {
    try {
        if (!msg.is_object() || msg.value("version", 0) != 1)
            throw std::runtime_error("不支持的控制协议版本");
        auto args = msg.value("arguments", json::object());
        if (!args.is_object())
            throw std::runtime_error("arguments 必须是对象");
        return {{"ok", true}, {"version", 1}, {"result", h.command(msg.at("command"), args)}};
    } catch (const std::exception &e) {
        return {{"ok", false}, {"version", 1}, {"error", e.what()}};
    }
}
std::wstring pipe_name(const fs::path &dir) {
    auto p = fs::absolute(dir).lexically_normal().wstring();
    CharLowerBuffW(p.data(), DWORD(p.size()));
    auto bytes = utf8(p);
    BCRYPT_ALG_HANDLE alg;
    BCRYPT_HASH_HANDLE hash;
    check(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr, 0));
    check(BCryptCreateHash(alg, &hash, nullptr, 0, nullptr, 0, 0));
    check(BCryptHashData(hash, reinterpret_cast<PUCHAR>(bytes.data()), ULONG(bytes.size()), 0));
    unsigned char digest[32];
    check(BCryptFinishHash(hash, digest, 32, 0));
    BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(alg, 0);
    std::wstring name = L"\\\\.\\pipe\\DualTone-";
    const wchar_t *hex = L"0123456789abcdef";
    for (int i = 0; i < 12; i++) {
        name += hex[digest[i] >> 4];
        name += hex[digest[i] & 15];
    }
    return name;
}
static bool io(HANDLE h, bool write, void *buffer, DWORD size, DWORD &done) {
    OVERLAPPED ov{};
    ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    BOOL ok = write ? WriteFile(h, buffer, size, &done, &ov) : ReadFile(h, buffer, size, &done, &ov);
    if (!ok && GetLastError() == ERROR_IO_PENDING) {
        if (WaitForSingleObject(ov.hEvent, ControlTimeoutMs) == WAIT_OBJECT_0)
            ok = GetOverlappedResult(h, &ov, &done, FALSE);
        else {
            CancelIoEx(h, &ov);
            GetOverlappedResult(h, &ov, &done, TRUE);
            ok = FALSE;
        }
    }
    CloseHandle(ov.hEvent);
    return ok;
}
std::optional<json> request(const fs::path &dir, const json &message) {
    auto name = pipe_name(dir);
    HANDLE pipe = CreateFileW(name.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING,
                              FILE_FLAG_OVERLAPPED, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) {
        if (GetLastError() == ERROR_PIPE_BUSY) {
            WaitNamedPipeW(name.c_str(), ControlTimeoutMs);
            pipe = CreateFileW(name.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING,
                               FILE_FLAG_OVERLAPPED, nullptr);
        }
        if (pipe == INVALID_HANDLE_VALUE)
            return {};
    }
    try {
        auto text = message.dump() + "\n";
        if (text.size() > MaxConfigBytes)
            throw std::runtime_error("请求过大");
        DWORD done;
        if (!io(pipe, true, text.data(), DWORD(text.size()), done) || done != text.size())
            throw std::runtime_error("发送控制请求失败");
        std::string result;
        char buffer[4096];
        while (result.find('\n') == std::string::npos) {
            if (!io(pipe, false, buffer, sizeof(buffer), done) || !done)
                throw std::runtime_error("控制接口未响应");
            result.append(buffer, done);
            if (result.size() > MaxConfigBytes)
                throw std::runtime_error("控制响应过大");
        }
        CloseHandle(pipe);
        return json::parse(result.substr(0, result.find('\n')));
    } catch (...) {
        CloseHandle(pipe);
        throw;
    }
}
static HANDLE make_pipe(const fs::path &dir) {
    HANDLE token = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token))
        throw std::runtime_error("无法读取当前用户");
    DWORD size = 0;
    GetTokenInformation(token, TokenUser, nullptr, 0, &size);
    std::vector<BYTE> data(size);
    if (!GetTokenInformation(token, TokenUser, data.data(), size, &size)) {
        CloseHandle(token);
        throw std::runtime_error("无法读取用户标识");
    }
    CloseHandle(token);
    LPWSTR sid = nullptr;
    ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER *>(data.data())->User.Sid, &sid);
    std::wstring acl = L"D:P(A;;GA;;;";
    acl += sid;
    acl += L")";
    LocalFree(sid);
    PSECURITY_DESCRIPTOR descriptor = nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(acl.c_str(), SDDL_REVISION_1, &descriptor,
                                                              nullptr))
        throw std::runtime_error("无法创建控制权限");
    SECURITY_ATTRIBUTES sa{sizeof(sa), descriptor, FALSE};
    HANDLE h =
        CreateNamedPipeW(pipe_name(dir).c_str(),
                         PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE,
                         PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS, 1,
                         DWORD(MaxConfigBytes), DWORD(MaxConfigBytes), ControlTimeoutMs, &sa);
    LocalFree(descriptor);
    return h;
}
Server::Server(Host &h) : host(h) {
    first = make_pipe(host.store.directory);
    if (first == INVALID_HANDLE_VALUE)
        throw std::runtime_error("此配置目录已有运行实例，请用 CLI 控制或先 shutdown");
    worker = std::thread([this] { run(); });
}
Server::~Server() {
    stop_flag = true;
    if (worker.joinable())
        worker.join();
    if (first != INVALID_HANDLE_VALUE)
        CloseHandle(first);
}
void Server::run() {
    while (!stop_flag && !host.quitting) {
        OVERLAPPED ov{};
        ov.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        BOOL connected = ConnectNamedPipe(first, &ov);
        auto err = GetLastError();
        if (!connected && err == ERROR_IO_PENDING) {
            while (!stop_flag && !host.quitting && WaitForSingleObject(ov.hEvent, 100) == WAIT_TIMEOUT) {
            }
            DWORD n;
            connected = GetOverlappedResult(first, &ov, &n, FALSE);
            if (!connected) {
                CancelIoEx(first, &ov);
                GetOverlappedResult(first, &ov, &n, TRUE);
            }
        } else if (err == ERROR_PIPE_CONNECTED)
            connected = TRUE;
        CloseHandle(ov.hEvent);
        if (!connected)
            continue;
        try {
            std::string msg;
            char buf[4096];
            DWORD got;
            while (msg.find('\n') == std::string::npos) {
                if (!io(first, false, buf, sizeof(buf), got) || !got)
                    throw std::runtime_error("请求读取失败");
                msg.append(buf, got);
                if (msg.size() > MaxConfigBytes)
                    throw std::runtime_error("请求过大");
            }
            auto r = envelope(host, json::parse(msg.substr(0, msg.find('\n')))).dump() + "\n";
            if (io(first, true, r.data(), DWORD(r.size()), got) && got == r.size()) {
                // DisconnectNamedPipe discards unread buffered data. The one-request
                // protocol's client closes only after consuming the response. Wait
                // for that EOF, bounded by ControlTimeoutMs, before disconnecting.
                char unused;
                io(first, false, &unused, 1, got);
            }
        } catch (...) {
        }
        DisconnectNamedPipe(first);
    }
}
static std::optional<std::wstring> reg_string(HKEY root, const std::wstring &path, const wchar_t *name) {
    DWORD size = 0, type = 0;
    if (RegGetValueW(root, path.c_str(), name, RRF_RT_REG_SZ | RRF_RT_REG_EXPAND_SZ, &type, nullptr,
                     &size) != ERROR_SUCCESS)
        return {};
    std::wstring data(size / 2, 0);
    if (RegGetValueW(root, path.c_str(), name, RRF_RT_REG_SZ | RRF_RT_REG_EXPAND_SZ, &type, data.data(),
                     &size) != ERROR_SUCCESS)
        return {};
    while (!data.empty() && data.back() == 0)
        data.pop_back();
    return data;
}
static json endpoint_effects(const std::string &id) {
    json r = {{"state", "read"},
              {"modules", json::array()},
              {"unresolved", json::array()},
              {"equalizer_apo_registered", false},
              {"note", "注册配置不能证明音效实时生效"}};
    auto start = id.rfind('{');
    if (start == std::string::npos) {
        r["state"] = "unknown";
        return r;
    }
    auto path = L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\MMDevices\\Audio\\Render\\" +
                wide(id.substr(start)) + L"\\FxProperties";
    HKEY key;
    auto err = RegOpenKeyExW(HKEY_LOCAL_MACHINE, path.c_str(), 0, KEY_READ, &key);
    if (err != ERROR_SUCCESS) {
        if (err != ERROR_FILE_NOT_FOUND)
            r["state"] = "unknown";
        return r;
    }
    std::regex guid("\\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\\}");
    for (DWORD i = 0;; i++) {
        wchar_t name[1024];
        BYTE bytes[16384];
        DWORD n = 1024, size = sizeof(bytes), type;
        auto e = RegEnumValueW(key, i, name, &n, nullptr, &type, bytes, &size);
        if (e == ERROR_NO_MORE_ITEMS)
            break;
        if (e != ERROR_SUCCESS || (type != REG_SZ && type != REG_MULTI_SZ && type != REG_EXPAND_SZ))
            continue;
        auto text = utf8(std::wstring_view(reinterpret_cast<wchar_t *>(bytes), size / 2));
        for (std::sregex_iterator it(text.begin(), text.end(), guid), end; it != end; ++it) {
            auto clsid = it->str();
            auto p =
                reg_string(HKEY_CLASSES_ROOT, L"CLSID\\" + wide(clsid) + L"\\InprocServer32", nullptr);
            if (p) {
                auto s = utf8(*p);
                if (std::find(r["modules"].begin(), r["modules"].end(), json(s)) == r["modules"].end())
                    r["modules"].push_back(s);
                std::transform(s.begin(), s.end(), s.begin(),
                               [](unsigned char c) { return char(tolower(c)); });
                if (s.find("equalizerapo") != std::string::npos)
                    r["equalizer_apo_registered"] = true;
            } else
                r["unresolved"].push_back(clsid);
        }
    }
    RegCloseKey(key);
    return r;
}
json effects_report(const json &cfg) {
    auto path = reg_string(HKEY_LOCAL_MACHINE, L"SOFTWARE\\EqualizerAPO", L"ConfigPath");
    json result = {{"equalizer_apo_installed", bool(path)},
                   {"config_path", nullptr},
                   {"configured_processing", json::array()},
                   {"config_error", ""},
                   {"main", endpoint_effects(cfg["source_id"])},
                   {"auxiliary", endpoint_effects(cfg["target_id"])},
                   {"scope", "只读检查；安装和挂载不等于实时生效，未检测应用内 EQ 或音箱内部音效。"}};
    if (path) {
        auto p = fs::path(*path) / L"config.txt";
        result["config_path"] = utf8(p.wstring());
        std::ifstream in(p);
        if (!in)
            result["config_error"] = "配置文件无法读取";
        std::string line;
        while (std::getline(in, line)) {
            auto pos = line.find_first_not_of(" \t");
            if (pos == std::string::npos)
                continue;
            line = line.substr(pos);
            if (line.starts_with("Filter:") || line.starts_with("Include:") ||
                line.starts_with("VSTPlugin:"))
                result["configured_processing"].push_back(line);
        }
    }
    return result;
}
} // namespace dt
