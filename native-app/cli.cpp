#include "core.hpp"
#include <iostream>
namespace dt {
int cli_main(int argc, wchar_t **argv) {
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
    try {
        fs::path dir = executable_dir() / L"data";
        int i = 1;
        if (i < argc && std::wstring(argv[i]) == L"--data-dir") {
            if (++i >= argc)
                throw std::runtime_error("缺少配置目录");
            dir = argv[i++];
        }
        std::string cmd = i < argc ? utf8(argv[i++]) : "--help";
        if (cmd == "--help" || cmd == "-h") {
            std::cout << "DualTone native CLI\nUsage: DualToneCLI [--data-dir PATH] COMMAND\nCommands: "
                         "devices schema get set (--json JSON|--file FILE) presets preset NAME "
                         "preset-add NAME preset-delete NAME effects start stop status latency "
                         "[--probe] pause on|off import FILE export FILE shutdown serve\n";
            return 0;
        }
        if (cmd == "serve") {
            Host h(dir);
            Server s(h);
            while (!h.quitting)
                Sleep(50);
            return 0;
        }
        json args = json::object();
        std::string command = cmd;
        fs::path file;
        auto next = [&]() {
            if (i >= argc)
                throw std::runtime_error("缺少命令参数");
            return std::wstring(argv[i++]);
        };
        if (cmd == "set") {
            auto option = next();
            if (option == L"--json")
                args = json::parse(utf8(next()));
            else if (option == L"--file")
                args = read_json(next());
            else
                throw std::runtime_error("set 需要 --json 或 --file");
            if (!args.is_object())
                throw std::runtime_error("设置补丁必须为对象");
        }
        if (cmd == "preset" || cmd == "preset-add" || cmd == "preset-delete")
            args["name"] = utf8(next());
        if (cmd == "pause") {
            auto value = next();
            if (value != L"on" && value != L"off")
                throw std::runtime_error("pause 需要 on 或 off");
            args["enabled"] = value == L"on";
        }
        if (cmd == "import") {
            auto doc = read_json(next());
            if (doc.at("version") != 1 && doc.at("version") != 2)
                throw std::runtime_error("不支持的预设版本");
            args = validate(doc.at("settings"));
            args.erase("source_id");
            args.erase("target_id");
            command = "set";
        }
        if (cmd == "export") {
            file = next();
            command = "get";
        }
        bool probe = false;
        if (cmd == "latency" && i < argc) {
            if (next() != L"--probe")
                throw std::runtime_error("未知测量参数");
            probe = true;
        }
        if (i != argc)
            throw std::runtime_error("多余的命令参数");
        json msg = {{"version", 1}, {"command", command}, {"arguments", args}}, result;
        if (cmd == "devices")
            result = {{"ok", true}, {"result", devices()}};
        else if (cmd == "schema") {
            Host h(dir);
            result = {{"ok", true}, {"result", h.schema()}};
        } else if (cmd == "latency") {
            auto state = request(dir, {{"version", 1}, {"command", "status"}});
            if (!state || !state->value("ok", false) ||
                (*state)["result"]["audio"]["state"] != "running" ||
                (*state)["result"]["paused"].get<bool>())
                throw std::runtime_error("请先启动补声并取消静音");
            auto cfg = (*state)["result"]["settings"];
            auto measurement = measure_latency(cfg, probe);
            auto after = request(dir, {{"version", 1}, {"command", "status"}});
            if (!after || (*after)["result"]["settings"] != cfg ||
                (*after)["result"]["audio"]["state"] != "running" ||
                (*after)["result"]["paused"].get<bool>())
                throw std::runtime_error("测量期间配置改变，请重新测量");
            result = {{"ok", true}, {"result", measurement}};
        } else {
            auto remote = request(dir, msg);
            if (!remote && cmd == "start") {
                fs::create_directories(dir);
                auto path = executable_dir() / L"DualToneCLI.exe";
                auto line = L"\"" + path.wstring() + L"\" --data-dir \"" + fs::absolute(dir).wstring() +
                            L"\" serve";
                STARTUPINFOW si{sizeof(si)};
                PROCESS_INFORMATION pi{};
                if (!CreateProcessW(path.c_str(), line.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW,
                                    nullptr, executable_dir().c_str(), &si, &pi))
                    throw std::runtime_error("后台服务启动失败");
                CloseHandle(pi.hThread);
                double end = clock_seconds() + 5;
                while (clock_seconds() < end) {
                    Sleep(50);
                    remote = request(dir, msg);
                    if (remote)
                        break;
                    if (WaitForSingleObject(pi.hProcess, 0) == WAIT_OBJECT_0)
                        break;
                }
                CloseHandle(pi.hProcess);
                if (!remote)
                    throw std::runtime_error("后台服务未就绪");
            }
            if (remote)
                result = *remote;
            else if (cmd == "status")
                result = {{"ok", true},
                          {"result", {{"running", false}, {"audio", {{"state", "offline"}}}}}};
            else if (command == "get" || command == "set" || command == "presets" ||
                     command == "preset" || command == "preset-add" || command == "preset-delete" ||
                     command == "effects") {
                Host h(dir);
                if (h.store.failed)
                    throw std::runtime_error(h.store.warning);
                result = envelope(h, msg);
                result["offline"] = true;
            } else
                throw std::runtime_error("没有运行中的 DualTone");
        }
        if (cmd == "export" && result.value("ok", false)) {
            save_json(file, {{"version", 2}, {"settings", result["result"]}});
            result["result"] = {{"exported", utf8(fs::absolute(file).wstring())}};
        }
        std::cout << result.dump(2) << std::endl;
        return result.value("ok", false) ? 0 : 1;
    } catch (const std::exception &e) {
        std::cout << json({{"ok", false}, {"error", e.what()}}).dump(2) << std::endl;
        return 1;
    }
}
} // namespace dt
int wmain(int argc, wchar_t **argv) {
    return dt::cli_main(argc, argv);
}
