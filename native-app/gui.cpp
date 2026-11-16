#include "core.hpp"
#include "ui.h"
#include <commdlg.h>
#include <functional>
#include <gdiplus.h>
#include <iomanip>
#include <shellapi.h>
#include <sstream>
using namespace dt;
static std::string str(const slint::SharedString &s) {
    return std::string(s.data(), s.size());
}
static slint::SharedString ss(std::string_view text) {
    return slint::SharedString(text);
}
static std::string fmt(double x, int digits = 1) {
    std::ostringstream s;
    s << std::fixed << std::setprecision(digits) << x;
    return s.str();
}
template <class T> static auto model(const std::vector<T> &items) {
    return std::make_shared<slint::VectorModel<T>>(items);
}
static slint::Image svg(const std::string &body, const char *color = "#70828e") {
    auto s = std::string("<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 "
                         "24 24'><g fill='none' stroke='") +
             color + "' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'>" + body +
             "</g></svg>";
    return slint::Image::load_from_data({reinterpret_cast<const uint8_t *>(s.data()), s.size()}, "svg");
}
static slint::Image icon(const std::string &name) {
    if (name == "headphones")
        return svg("<path d='M4 14v-4a8 8 0 0116 0v4'/><rect x='3' y='12' width='4' height='8' "
                   "rx='2'/><rect x='17' y='12' width='4' height='8' rx='2'/>");
    if (name == "monitor")
        return svg("<rect x='3' y='4' width='18' height='13' rx='2'/><path d='M12 17v4M8 21h8'/>");
    if (name == "speaker")
        return svg("<path d='M4 9h4l5-4v14l-5-4H4zM17 8q7 4 0 8'/>");
    if (name == "sliders")
        return svg("<path d='M5 3v5m0 4v9M12 3v11m0 4v3M19 3v3m0 4v11'/><rect x='2' y='8' width='6' "
                   "height='4' rx='1'/><rect x='9' y='14' width='6' height='4' rx='1'/><rect x='16' "
                   "y='6' width='6' height='4' rx='1'/>",
                   "#36aa96");
    if (name == "line")
        return svg("<path d='M9 3v4M15 3v4M12 15v6'/><rect x='7' y='7' width='10' height='8' rx='2'/>");
    if (name == "digital")
        return svg("<rect x='3' y='6' width='18' height='12' rx='3'/><path d='M7 10h10M7 14h5'/>");
    return svg("<path d='M4 10v4M9 4v16M15 7v10M20 10v4'/>");
}
static slint::Image logo() {
    std::string s = "<svg xmlns='http://www.w3.org/2000/svg' width='34' height='34'><rect width='34' "
                    "height='34' rx='9' fill='#237f6f'/><path d='M8 14v6m6-12v18m6-14v10m6-7v4' "
                    "fill='none' stroke='white' stroke-width='1.7' stroke-linecap='round'/></svg>";
    return slint::Image::load_from_data({reinterpret_cast<const uint8_t *>(s.data()), s.size()}, "svg");
}
static slint::Image chart_image(const Dsp &dsp, const std::vector<std::array<double, 4>> &data,
                                bool mini) {
    using namespace Gdiplus;
    int width = mini ? 400 : 900, height = mini ? 170 : 300;
    std::vector<BYTE> bgra(width * height * 4);
    Bitmap bitmap(width, height, width * 4, PixelFormat32bppARGB, bgra.data());
    Graphics g(&bitmap);
    g.Clear(Color(255, 24, 33, 37));
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintAntiAliasGridFit);
    Font font(L"Microsoft YaHei UI", mini ? 9.f : 10.f, FontStyleRegular, UnitPixel);
    SolidBrush muted(Color(255, 166, 185, 195));
    float left = mini ? 30.f : 38.f, top = mini ? 22.f : 24.f, right = width - (mini ? 26.f : 32.f),
          bottom = height - 24.f;
    auto xp = [&](double hz) { return left + float(log(hz / 20) / log(1000)) * (right - left); };
    auto yp = [&](double db) {
        return top + float((12 - std::clamp(db, -36., 12.)) / 48) * (bottom - top);
    };
    Pen grid(Color(255, 43, 57, 63), 1), zero(Color(255, 66, 81, 89), 1);
    for (int db : {12, 0, -12, -24, -36}) {
        auto y = yp(db);
        g.DrawLine(db == 0 ? &zero : &grid, left, y, right, y);
        auto t = wide((db >= 0 ? "+" : "") + std::to_string(db));
        g.DrawString(t.c_str(), -1, &font, PointF(3, y - 6), &muted);
    }
    for (int hz : {32, 125, 500, 2000, 8000}) {
        auto x = xp(hz);
        g.DrawLine(&grid, x, top, x, bottom);
        auto t = wide(hz < 1000 ? std::to_string(hz) : std::to_string(hz / 1000) + "k");
        g.DrawString(t.c_str(), -1, &font, PointF(x - 10, bottom + 7), &muted);
    }
    g.DrawString(L"dB", -1, &font, PointF(3, 3), &muted);
    g.DrawString(L"dBFS", -1, &font, PointF(right + 3, 3), &muted);
    for (int db : {0, -30, -60, -90}) {
        auto t = wide(std::to_string(db));
        g.DrawString(t.c_str(), -1, &font, PointF(right + 3, top + (-db) / 90.f * (bottom - top) - 5),
                     &muted);
    }
    if (data.size() >= 256) {
        size_t n = AnalysisFrames;
        std::array<std::vector<Complex>, 4> spectra;
        for (int c = 0; c < 4; c++) {
            spectra[c].resize(n);
            for (size_t i = 0; i < std::min(n, data.size()); i++)
                spectra[c][i] = data[i][c] * (.5 - .5 * cos(2 * std::numbers::pi * i / (n - 1)));
            fft(spectra[c]);
        }
        for (int channel = 0; channel < 4; channel += 2) {
            std::vector<PointF> points;
            for (int i = 0; i < 320; i++) {
                double f = 20 * pow(1000., i / 319.), bin = f * n / ProcessingRate;
                size_t b = std::clamp<size_t>(size_t(bin), 1, n / 2 - 1);
                double v = std::max(abs(spectra[channel][b]), abs(spectra[channel + 1][b])) * 4 / n;
                double db = std::clamp(20 * log10(std::max(v, 1e-9)), -90., 0.);
                points.push_back({xp(f), top + float(-db / 90) * (bottom - top)});
            }
            Pen pen(channel ? Color(255, 70, 200, 178) : Color(255, 139, 162, 175), mini ? .8f : 1.f);
            g.DrawLines(&pen, points.data(), INT(points.size()));
        }
    }
    for (int curve = 0; curve < 2; curve++) {
        std::vector<PointF> points;
        for (int i = 0; i < 600; i++) {
            double f = 20 * pow(1000., i / 599.);
            auto h = dsp.cfg["eq_enabled"].get<bool>() ? dsp.eq_response(f) : Complex(1);
            if (curve)
                h *= dsp.band_response(f);
            points.push_back({xp(f), yp(20 * log10(std::max(abs(h), 1e-12)))});
        }
        Pen p(curve ? Color(255, 185, 175, 124) : Color(255, 255, 196, 81), curve ? 1.3f : 1.8f);
        if (curve)
            p.SetDashStyle(DashStyleDash);
        g.DrawLines(&p, points.data(), INT(points.size()));
    }
    slint::SharedPixelBuffer<slint::Rgba8Pixel> pixels(width, height);
    for (size_t i = 0; i < pixels.width() * pixels.height(); i++)
        pixels.begin()[i] = {bgra[i * 4 + 2], bgra[i * 4 + 1], bgra[i * 4], bgra[i * 4 + 3]};
    return slint::Image(pixels);
}
static void snapshot(const slint::Window &w, const fs::path &path) {
    auto pixels = w.take_snapshot();
    if (!pixels)
        return;
    fs::create_directories(path.parent_path());
    std::vector<BYTE> bgra(pixels->width() * pixels->height() * 4);
    for (size_t i = 0; i < bgra.size() / 4; i++) {
        auto p = pixels->begin()[i];
        bgra[i * 4] = p.b;
        bgra[i * 4 + 1] = p.g;
        bgra[i * 4 + 2] = p.r;
        bgra[i * 4 + 3] = p.a;
    }
    Gdiplus::Bitmap image(pixels->width(), pixels->height(), pixels->width() * 4, PixelFormat32bppARGB,
                          bgra.data());
    UINT count, bytes;
    Gdiplus::GetImageEncodersSize(&count, &bytes);
    std::vector<BYTE> encoders(bytes);
    auto enc = reinterpret_cast<Gdiplus::ImageCodecInfo *>(encoders.data());
    Gdiplus::GetImageEncoders(count, bytes, enc);
    for (UINT i = 0; i < count; i++)
        if (wcscmp(enc[i].MimeType, L"image/png") == 0) {
            image.Save(path.c_str(), &enc[i].Clsid);
            break;
        }
}
static bool system_dark() {
    DWORD value = 1, size = sizeof(value);
    RegGetValueW(HKEY_CURRENT_USER, L"Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize",
                 L"AppsUseLightTheme", RRF_RT_REG_DWORD, nullptr, &value, &size);
    return value == 0;
}
static std::optional<fs::path> file_dialog(HWND parent, bool save) {
    wchar_t path[32768] = L"";
    OPENFILENAMEW ofn{sizeof(ofn)};
    ofn.hwndOwner = parent;
    ofn.lpstrFilter = L"DualTone 预设 (*.json)\0*.json\0\0";
    ofn.lpstrFile = path;
    ofn.nMaxFile = 32768;
    ofn.lpstrDefExt = L"json";
    ofn.Flags = OFN_NOCHANGEDIR | OFN_PATHMUSTEXIST | (save ? OFN_OVERWRITEPROMPT : OFN_FILEMUSTEXIST);
    if (save ? GetSaveFileNameW(&ofn) : GetOpenFileNameW(&ofn))
        return fs::path(path);
    return {};
}
static std::function<void(int)> tray_action;
static LRESULT CALLBACK tray_proc(HWND h, UINT msg, WPARAM w, LPARAM l) {
    if (msg == WM_APP + 1) {
        if (l == WM_LBUTTONUP || l == WM_LBUTTONDBLCLK)
            tray_action(1);
        if (l == WM_RBUTTONUP) {
            HMENU menu = CreatePopupMenu();
            AppendMenuW(menu, MF_STRING, 1, L"打开 DualTone");
            AppendMenuW(menu, MF_STRING, 2, L"开始 / 停止补声");
            AppendMenuW(menu, MF_STRING, 3, L"静音 / 恢复补声");
            AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
            AppendMenuW(menu, MF_STRING, 4, L"退出");
            POINT p;
            GetCursorPos(&p);
            SetForegroundWindow(h);
            int selected =
                TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON, p.x, p.y, 0, h, nullptr);
            DestroyMenu(menu);
            if (selected)
                tray_action(selected);
        }
        return 0;
    }
    return DefWindowProcW(h, msg, w, l);
}
class Ui {
  public:
    Host host;
    Server server;
    slint::ComponentHandle<MainWindow> main = MainWindow::create();
    slint::ComponentHandle<EditorWindow> editor = EditorWindow::create();
    slint::ComponentHandle<InfoWindow> info = InfoWindow::create();
    json device_rows = json::array();
    std::vector<std::string> labels;
    std::string issue;
    uint64_t revision = UINT64_MAX;
    bool editor_visible = false, main_visible = true, force_dark = false;
    std::atomic_bool measuring = false;
    std::thread measurement;
    slint::Timer timer;
    NOTIFYICONDATAW tray{};
    HWND tray_window = nullptr;
    std::shared_ptr<slint::VectorModel<EqPoint>> points = model(std::vector<EqPoint>{});
    std::shared_ptr<slint::VectorModel<BandRow>> bands = model(std::vector<BandRow>{});
    explicit Ui(fs::path dir, bool dark) : host(dir), server(host), force_dark(dark) {
        auto log = logo();
        for (auto *g : {&main->global<UiData>(), &editor->global<UiData>(), &info->global<UiData>()}) {
            g->set_minimum_body(float(100 * pow(10., -MidCutDb / 20)));
            g->set_logo(log);
            g->set_sliders_icon(icon("sliders"));
            g->set_eq_points(points);
            g->set_bands(bands);
            bind(*g);
        }
        editor->global<UiData>().set_dark(true);
        editor->set_scheme(slint::cbindgen_private::ColorScheme::Dark);
        info->set_scheme(slint::cbindgen_private::ColorScheme::Light);
        issue = host.store.warning;
        refresh();
        main->show();
        editor->window().on_close_requested([this] {
            editor_visible = false;
            editor->hide();
            return slint::CloseRequestResponse::KeepWindowShown;
        });
        info->window().on_close_requested([this] {
            info->hide();
            return slint::CloseRequestResponse::KeepWindowShown;
        });
        main->window().on_close_requested([this] {
            host.quitting = true;
            return slint::CloseRequestResponse::HideWindow;
        });
        WNDCLASSW wc{};
        wc.lpfnWndProc = tray_proc;
        wc.hInstance = GetModuleHandleW(nullptr);
        wc.lpszClassName = L"DualToneNativeTray";
        RegisterClassW(&wc);
        tray_window = CreateWindowW(wc.lpszClassName, L"", 0, 0, 0, 0, 0, HWND_MESSAGE, nullptr,
                                    wc.hInstance, nullptr);
        tray.cbSize = sizeof(tray);
        tray.hWnd = tray_window;
        tray.uID = 1;
        tray.uFlags = NIF_ICON | NIF_TIP | NIF_MESSAGE;
        tray.uCallbackMessage = WM_APP + 1;
        tray.hIcon = LoadIconW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(101));
        SendMessageW(main->window().win32_hwnd(),WM_SETICON,ICON_SMALL,reinterpret_cast<LPARAM>(tray.hIcon));
        SendMessageW(main->window().win32_hwnd(),WM_SETICON,ICON_BIG,reinterpret_cast<LPARAM>(tray.hIcon));
        wcscpy_s(tray.szTip, L"DualTone");
        Shell_NotifyIconW(NIM_ADD, &tray);
        tray_action = [this](int c) {
            if (c == 1) {
                main_visible = true;
                main->show();
                SetForegroundWindow(main->window().win32_hwnd());
            }
            if (c == 2)
                action("toggle", "");
            if (c == 3)
                action("pause", "");
            if (c == 4) {
                host.quitting = true;
                slint::quit_event_loop();
            }
        };
        tick();
        timer.start(slint::TimerMode::Repeated, std::chrono::milliseconds(100), [this] { tick(); });
    }
    ~Ui() {
        timer.stop();
        host.quitting = true;
        if (measurement.joinable())
            measurement.join();
        Shell_NotifyIconW(NIM_DELETE, &tray);
        if (tray_window)
            DestroyWindow(tray_window);
    }
    void failure(const std::exception &e) {
        issue = e.what();
        revision = UINT64_MAX;
    }
    void bind(const UiData &g) {
        g.on_action(
            [this](slint::SharedString c, slint::SharedString arg) { action(str(c), str(arg)); });
        g.on_setting([this](slint::SharedString k, slint::SharedString v) {
            try {
                setting(str(k), str(v));
                issue.clear();
            } catch (const std::exception &e) {
                failure(e);
            }
            tick();
        });
        g.on_eq_edit([this](int i, float v) {
            try {
                if (i < 0 || i >= 10)
                    return;
                auto gains = host.command("get")["gains"];
                gains[i] = round(std::clamp(double(v), -12., 12.) * 10) / 10;
                host.command("set", {{"gains", gains}});
                issue.clear();
            } catch (const std::exception &e) {
                failure(e);
            }
            tick();
        });
        g.on_band_edit([this](int i, slint::SharedString k, slint::SharedString v) {
            try {
                auto rows = host.command("get")["bands"];
                rows.at(i)[str(k)] = json::parse(str(v));
                host.command("set", {{"bands", rows}});
                issue.clear();
            } catch (const std::exception &e) {
                failure(e);
            }
            tick();
        });
    }
    void setting(std::string k, std::string value) {
        auto v = json::parse(value);
        if (k == "body") {
            double body = v;
            host.command("set", {{"spatial_strength",
                                  std::clamp(-20 * log10(body / 100) / MidCutDb * 100, 0., 100.)}});
        } else if (k.starts_with("eq-")) {
            auto g = host.command("get")["gains"];
            g.at(std::stoi(k.substr(3))) = v;
            host.command("set", {{"gains", g}});
        } else
            host.command("set", {{k, v}});
    }
    void refresh() {
        device_rows = devices();
        labels = {"选择设备"};
        for (auto &d : device_rows) {
            auto s = d["name"].get<std::string>();
            if (!d["supported"].get<bool>())
                s += " · " + d["reason"].get<std::string>();
            labels.push_back(s);
        }
        std::vector<slint::SharedString> l;
        for (auto &s : labels)
            l.emplace_back(s);
        auto rows = model(l);
        main->global<UiData>().set_device_labels(rows);
        editor->global<UiData>().set_device_labels(rows);
        revision = UINT64_MAX;
    }
    void dialog(std::string title, std::string text, bool input = false) {
        auto &g = info->global<UiData>();
        g.set_dialog_title(ss(title));
        g.set_dialog_text(ss(text));
        g.set_dialog_input(input);
        g.set_dark(force_dark || system_dark());
        info->set_scheme((force_dark || system_dark()) ? slint::cbindgen_private::ColorScheme::Dark
                                                       : slint::cbindgen_private::ColorScheme::Light);
        info->set_name("");
        info->show();
        SetForegroundWindow(info->window().win32_hwnd());
    }
    void action(std::string c, std::string value) {
        try {
            if (c == "toggle")
                host.command(host.engine.active ? "stop" : "start");
            else if (c == "pause")
                host.command("pause", {{"enabled", !host.engine.paused.load()}});
            else if (c == "refresh")
                refresh();
            else if (c == "source" || c == "target") {
                auto it = std::find(labels.begin(), labels.end(), value);
                if (it == labels.end() || it == labels.begin())
                    return;
                auto &d = device_rows[std::distance(labels.begin(), it) - 1];
                if (!d["supported"].get<bool>())
                    throw std::runtime_error(d["reason"]);
                host.command("set", {{c == "source" ? "source_id" : "target_id", d["id"]}});
            } else if (c == "swap") {
                auto cfg = host.command("get");
                host.command("set", {{"source_id", cfg["target_id"]}, {"target_id", cfg["source_id"]}});
            } else if (c == "details") {
                editor_visible = true;
                editor->show();
                SetForegroundWindow(editor->window().win32_hwnd());
            } else if (c == "tray") {
                main_visible = false;
                editor_visible = false;
                main->hide();
                editor->hide();
            } else if (c == "preset")
                host.command("preset", {{"name", value}});
            else if (c == "add-preset")
                dialog("新增预设", "保存当前声音设置，设备选择仍以当前电脑为准。", true);
            else if (c == "confirm-preset") {
                host.command("preset-add", {{"name", value}});
                info->hide();
            } else if (c == "delete-preset") {
                auto index = main->global<UiData>().get_preset_index();
                auto names = main->global<UiData>().get_presets();
                if (index >= 0 && index < names->row_count())
                    host.command("preset-delete", {{"name", str(*names->row_data(index))}});
            } else if (c == "close-info")
                info->hide();
            else if (c == "about")
                dialog("关于 DualTone", "DualTone 0.3.0 · 原生轻量版\nC++ + Slint · "
                                        "WASAPI\n\n主音频直出，副音频独立处理。\n支持旧配置迁移与 JSON CLI "
                                        "v0.1。\n\nhttps://github.com/Wu-Tea/DualTone");
            else if (c == "eq-reset")
                host.command("set", {{"gains", std::vector<double>(10, 0)}});
            else if (c == "band-add") {
                auto b = host.command("get")["bands"];
                b.push_back({{"low", 2000.0}, {"high", 5000.0}, {"gain_db", 0.0}, {"enabled", false}});
                host.command("set", {{"bands", b}});
            } else if (c == "band-delete") {
                auto b = host.command("get")["bands"];
                b.erase(size_t(std::stoi(value)));
                host.command("set", {{"bands", b}});
            } else if (c == "import" || c == "export") {
                auto p = file_dialog(editor->window().win32_hwnd(), c == "export");
                if (p) {
                    if (c == "export")
                        save_json(*p, {{"version", ConfigVersion}, {"settings", host.command("get")}});
                    else {
                        auto doc = read_json(*p);
                        if (doc.at("version") < 1 || doc.at("version") > ConfigVersion)
                            throw std::runtime_error("不支持的预设版本");
                        auto cfg = validate(doc.at("settings"));
                        cfg.erase("source_id");
                        cfg.erase("target_id");
                        host.command("set", cfg);
                    }
                }
            } else if (c == "effects") {
                auto r = host.command("effects");
                std::string text;
                for (auto k : {"main", "auxiliary"}) {
                    text += std::string(k == std::string("main") ? "主音频：" : "副音频：") +
                            (r[k].value("equalizer_apo_registered", false)
                                 ? "发现 Equalizer APO 挂载配置"
                                 : "未发现 Equalizer APO 挂载配置") +
                            "\n";
                    for (auto &m : r[k]["modules"])
                        text += utf8(fs::path(wide(m.get<std::string>())).filename().wstring()) + "\n";
                }
                text += "\n" + r["scope"].get<std::string>();
                for (auto &line : r["configured_processing"])
                    text += "\n" + line.get<std::string>();
                dialog("本机音效", text);
            } else if (c == "latency") {
                if (!host.engine.active || host.engine.paused)
                    throw std::runtime_error("请先启动补声并取消静音");
                if (measuring)
                    return;
                if (measurement.joinable())
                    measurement.join();
                auto cfg = host.command("get");
                measuring = true;
                dialog("数字延迟测量", "正在比较两路数字音频，约需 4 秒…");
                measurement = std::thread([this, cfg] {
                    std::string text;
                    try {
                        auto r = measure_latency(cfg, false);
                        if (host.command("get") != cfg || !host.engine.active || host.engine.paused)
                            throw std::runtime_error("测量期间设置或播放状态改变，请重试");
                        text = r["reliable"].get<bool>()
                                   ? "数字转发：" + fmt(r["transport_lag_ms"]) + " ms\n"
                                   : "本次相关性或时间戳不满足可靠性要求。\n";
                        text += "相关性：" + fmt(r["correlation"], 3) + "\n\n" +
                                r["note"].get<std::string>();
                    } catch (const std::exception &e) {
                        text = e.what();
                    }
                    slint::invoke_from_event_loop([this, text] {
                        info->global<UiData>().set_dialog_text(ss(text));
                        measuring = false;
                    });
                });
            }
            issue.clear();
        } catch (const std::exception &e) {
            failure(e);
        }
        tick();
    }
    void tick() {
        if (host.quitting) {
            slint::quit_event_loop();
            return;
        }
        std::lock_guard lock(host.mutex);
        bool dark = force_dark || system_dark();
        main->global<UiData>().set_dark(dark);
        main->set_scheme(dark ? slint::cbindgen_private::ColorScheme::Dark
                              : slint::cbindgen_private::ColorScheme::Light);
        auto state = host.engine.status();
        auto cfg = host.store.current;
        if (revision != host.revision) {
            revision = host.revision;
            std::vector<EqPoint> ps;
            for (int i = 0; i < 10; i++) {
                double v = cfg["gains"][i];
                ps.push_back(
                    {ss(EqFrequencies[i] < 1000 ? std::to_string(EqFrequencies[i])
                                                : std::to_string(EqFrequencies[i] / 1000) + "k"),
                     float(v), ss(fmt(v)), float(log(EqFrequencies[i] / 20.) / log(1000.))});
            }
            if (points->row_count() != ps.size())
                points->set_vector(ps);
            else
                for (size_t i = 0; i < ps.size(); i++)
                    if (*points->row_data(i) != ps[i])
                        points->set_row_data(i, ps[i]);
            std::vector<BandRow> bs;
            for (auto &b : cfg["bands"])
                bs.push_back({ss(fmt(b["low"], 0)), ss(fmt(b["high"], 0)), ss(fmt(b["gain_db"])),
                              b["enabled"].get<bool>()});
            if (bands->row_count() != bs.size())
                bands->set_vector(bs);
            else
                for (size_t i = 0; i < bs.size(); i++)
                    if (*bands->row_data(i) != bs[i])
                        bands->set_row_data(i, bs[i]);
            std::vector<slint::SharedString> names;
            int index = -1;
            for (auto &[name, preset] : host.store.presets.items()) {
                auto a = cfg, b = preset;
                for (auto k : {"source_id", "target_id"}) {
                    a.erase(k);
                    b.erase(k);
                }
                if (a == b)
                    index = int(names.size());
                names.emplace_back(name);
            }
            auto presets = model(names);
            for (auto *g : {&main->global<UiData>(), &editor->global<UiData>()}) {
                g->set_gain(cfg["gain"]);
                g->set_reverb(cfg["effect_mode"] == "reverb");
                g->set_reverb_size(cfg["reverb_size"]);
                g->set_reverb_decay(cfg["reverb_decay"]);
                g->set_reverb_brightness(cfg["reverb_brightness"]);
                g->set_body(
                    float(100 * pow(10., -MidCutDb * cfg["spatial_strength"].get<double>() / 100 / 20)));
                g->set_eq_on(cfg["eq_enabled"]);
                g->set_band_on(cfg["band_enabled"]);
                g->set_presets(presets);
                g->set_preset_index(index);
                g->set_preset_placeholder(names.empty() ? "尚无预设" : "未保存为预设");
                g->set_source_index(0);
                g->set_target_index(0);
                g->set_source_icon(icon("wave"));
                g->set_target_icon(icon("wave"));
                for (size_t i = 0; i < device_rows.size(); i++) {
                    auto &row = device_rows[i];
                    if (row["id"] == cfg["source_id"]) {
                        g->set_source_index(int(i) + 1);
                        g->set_source_icon(icon(row["icon"]));
                    }
                    if (row["id"] == cfg["target_id"]) {
                        g->set_target_index(int(i) + 1);
                        g->set_target_icon(icon(row["icon"]));
                    }
                }
                auto d = host.engine.dsp.load();
                g->set_headroom(ss("余量 " + fmt(-d->preamp_db) + " dB"));
            }
        }
        for (auto *g : {&main->global<UiData>(), &editor->global<UiData>()}) {
            g->set_active(host.engine.active);
            g->set_paused(host.engine.paused);
            g->set_status(host.engine.active ? "补声中" : "已停止");
            g->set_input_level(float(std::min(1., state.value("input_peak", 0.) * 3)));
            g->set_output_level(float(std::min(1., state.value("output_peak", 0.) * 3)));
            g->set_queue(ss("队列 " + fmt(state.value("queue_ms", 0.)) + " ms   不连续 " +
                            std::to_string(state.value("discontinuities", 0))));
            g->set_issue(ss(!issue.empty()                        ? issue
                            : state.value("state", "") == "error" ? state.value("message", "")
                                                                  : ""));
        }
        host.engine.analysis = main_visible || editor_visible;
        if (main_visible || editor_visible) {
            auto data = host.engine.spectrum_samples();
            auto dsp = host.engine.dsp.load();
            if (main_visible)
                main->global<UiData>().set_mini_chart(chart_image(*dsp, data, true));
            if (editor_visible)
                editor->global<UiData>().set_chart(chart_image(*dsp, data, false));
        }
    }
};
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    ULONG_PTR gdip;
    Gdiplus::GdiplusStartupInput startup;
    Gdiplus::GdiplusStartup(&gdip, &startup, nullptr);
    int code = 0;
    try {
        int argc;
        auto argv = CommandLineToArgvW(GetCommandLineW(), &argc);
        fs::path dir = executable_dir() / L"data", shot;
        double quit_after = 0;
        bool details = false, dark = false, start = false;
        int width = 0, editor_width = 0, editor_height = 0;
        for (int i = 1; i < argc; i++) {
            std::wstring a = argv[i];
            if (a == L"--data-dir" && i + 1 < argc)
                dir = argv[++i];
            else if (a == L"--details")
                details = true;
            else if (a == L"--dark")
                dark = true;
            else if (a == L"--start-audio")
                start = true;
            else if (a == L"--screenshot" && i + 1 < argc)
                shot = argv[++i];
            else if (a == L"--quit-after" && i + 1 < argc)
                quit_after = std::stod(argv[++i]);
            else if (a == L"--width" && i + 1 < argc)
                width = std::stoi(argv[++i]);
            else if (a == L"--editor-width" && i + 1 < argc)
                editor_width = std::stoi(argv[++i]);
            else if (a == L"--editor-height" && i + 1 < argc)
                editor_height = std::stoi(argv[++i]);
        }
        LocalFree(argv);
        Ui ui(dir, dark);
        if (width)
            ui.main->window().set_size(slint::LogicalSize{{float(width), 800.f}});
        if (editor_width || editor_height)
            ui.editor->window().set_size(slint::LogicalSize{{float(editor_width ? editor_width : 940),
                                                            float(editor_height ? editor_height : 760)}});
        if (details)
            ui.action("details", "");
        if (start)
            ui.action("toggle", "");
        slint::Timer capture, quit;
        if (!shot.empty())
            capture.start(slint::TimerMode::SingleShot, std::chrono::milliseconds(1500), [&] {
                snapshot(ui.main->window(), shot);
                auto state_path = shot;
                state_path.replace_extension("json");
                save_json(state_path,
                          {{"source_index", ui.main->global<UiData>().get_source_index()},
                           {"target_index", ui.main->global<UiData>().get_target_index()},
                           {"preset_index", ui.main->global<UiData>().get_preset_index()},
                           {"editor_preset_index", ui.editor->global<UiData>().get_preset_index()},
                           {"reverb", ui.main->global<UiData>().get_reverb()},
                           {"reverb_size", ui.main->global<UiData>().get_reverb_size()},
                           {"reverb_decay", ui.main->global<UiData>().get_reverb_decay()}});
                if (details) {
                    auto p = shot.parent_path() / (shot.stem().wstring() + L"-details.png");
                    snapshot(ui.editor->window(), p);
                }
            });
        if (quit_after > 0)
            quit.start(slint::TimerMode::SingleShot, std::chrono::milliseconds(int(quit_after * 1000)),
                       [&] {
                           ui.host.quitting = true;
                           slint::quit_event_loop();
                       });
        slint::run_event_loop(slint::EventLoopMode::RunUntilQuit);
    } catch (const std::exception &e) {
        MessageBoxW(nullptr, wide(e.what()).c_str(), L"DualTone", MB_OK | MB_ICONERROR);
        code = 1;
    }
    Gdiplus::GdiplusShutdown(gdip);
    return code;
}
