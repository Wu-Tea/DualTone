#pragma once
#include <commctrl.h>
#include <dwmapi.h>
#include <functional>
#include <windowsx.h>

// Keep the native resize, taskbar, system-menu and snapping contracts; only
// replace non-client painting. All measurements originate in the Slint theme.
struct WindowFrame {
    float caption, button;
    std::function<void(bool)> hover;
    bool hovering = false;
    void set_hover(bool value) {
        if (hovering != value) { hovering = value; hover(value); }
    }
    static LRESULT CALLBACK procedure(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp,
                                      UINT_PTR id, DWORD_PTR data) {
        auto *frame = reinterpret_cast<WindowFrame *>(data);
        const UINT dpi = GetDpiForWindow(hwnd);
        const int border = GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi) +
                           GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi);
        if (msg == WM_NCCALCSIZE && wp) {
            if (IsZoomed(hwnd)) {
                auto &r = reinterpret_cast<NCCALCSIZE_PARAMS *>(lp)->rgrc[0];
                InflateRect(&r, -border, -border);
            }
            return 0;
        }
        if (msg == WM_NCHITTEST) {
            POINT p{GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
            ScreenToClient(hwnd, &p);
            RECT r{}; GetClientRect(hwnd, &r);
            if (!IsZoomed(hwnd)) {
                bool l = p.x < border, t = p.y < border;
                bool right = p.x >= r.right - border, bottom = p.y >= r.bottom - border;
                if (t && l) return HTTOPLEFT;
                if (t && right) return HTTOPRIGHT;
                if (bottom && l) return HTBOTTOMLEFT;
                if (bottom && right) return HTBOTTOMRIGHT;
                if (l) return HTLEFT;
                if (right) return HTRIGHT;
                if (t) return HTTOP;
                if (bottom) return HTBOTTOM;
            }
            const float scale = float(dpi) / 96;
            if (p.y < frame->caption * scale) {
                if (p.x < r.right - 3 * frame->button * scale) return HTCAPTION;
                if (p.x >= r.right - 2 * frame->button * scale &&
                    p.x < r.right - frame->button * scale) return HTMAXBUTTON;
            }
            return HTCLIENT;
        }
        if (msg == WM_NCMOUSEMOVE) {
            frame->set_hover(wp == HTMAXBUTTON);
            TRACKMOUSEEVENT tracking{sizeof(tracking), TME_LEAVE | TME_NONCLIENT, hwnd, 0};
            TrackMouseEvent(&tracking);
        }
        if (msg == WM_NCMOUSELEAVE || msg == WM_MOUSEMOVE) frame->set_hover(false);
        if (msg == WM_NCLBUTTONDOWN && wp == HTMAXBUTTON) return 0;
        if (msg == WM_NCLBUTTONUP && wp == HTMAXBUTTON) {
            PostMessageW(hwnd, WM_SYSCOMMAND, IsZoomed(hwnd) ? SC_RESTORE : SC_MAXIMIZE, 0);
            return 0;
        }
        if (msg == WM_NCDESTROY) {
            RemoveWindowSubclass(hwnd, procedure, id);
            delete frame;
        }
        return DefSubclassProc(hwnd, msg, wp, lp);
    }
    template<class Component> static void install(Component component) {
        auto hwnd = component->window().win32_hwnd();
        if (!hwnd) return; // Slint may materialize the native window on its first event-loop turn.
        DWORD_PTR previous{};
        if (GetWindowSubclass(hwnd, procedure, 1, &previous)) return;
        const auto size = component->window().size();
        auto frame = new WindowFrame{component->template global<Theme>().get_caption_height(),
                                     component->template global<Theme>().get_caption_button_width(),
                                     [weak = slint::ComponentWeakHandle(component)](bool hover) { if (auto alive = weak.lock()) (*alive)->template global<UiData>().set_caption_max_hover(hover); }};
        if (!SetWindowSubclass(hwnd, procedure, 1, reinterpret_cast<DWORD_PTR>(frame))) {
            delete frame;
            throw std::runtime_error("无法初始化自定义标题栏，Windows 错误 " + std::to_string(GetLastError()) + ", owner " + std::to_string(GetWindowThreadProcessId(hwnd, nullptr)) + ", current " + std::to_string(GetCurrentThreadId()));
        }
        SetWindowPos(hwnd, nullptr, 0, 0, size.width, size.height,
                     SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);
        MARGINS margins{1, 1, 1, 1}; DwmExtendFrameIntoClientArea(hwnd, &margins);
    }
};
