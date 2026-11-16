#include "core.hpp"
#include <iostream>
using namespace dt;
int main() {
    try {
        json input;
        std::cin >> input;
        auto command = input.at("command").get<std::string>();
        json output;
        if (command == "dsp") {
            auto d = std::make_shared<Dsp>(input.at("settings"));
            Processor p;
            p.update(d);
            auto audio = input.at("samples").get<std::vector<double>>();
            p.process(audio, false);
            output["samples"] = audio;
            output["preamp_db"] = d->preamp_db;
            json eq = json::array(), band = json::array();
            for (double f : input.at("frequencies")) {
                auto e = d->eq_response(f), b = d->band_response(f);
                eq.push_back({e.real(), e.imag()});
                band.push_back({b.real(), b.imag()});
            }
            output["eq"] = eq;
            output["band"] = band;
        } else if (command == "resample") {
            Resampler r(input.at("source"), input.at("target"));
            std::vector<double> out;
            for (auto &packet : input.at("packets")) {
                auto p = r.process(packet.get<std::vector<double>>());
                out.insert(out.end(), p.begin(), p.end());
            }
            output["samples"] = out;
        } else if (command == "validate")
            output = validate(input.at("settings"));
        else if (command == "pipe")
            output = utf8(pipe_name(wide(input.at("directory").get<std::string>())));
        else
            throw std::runtime_error("unknown test command");
        std::cout << json({{"ok", true}, {"result", output}}).dump();
        return 0;
    } catch (const std::exception &e) {
        std::cout << json({{"ok", false}, {"error", e.what()}}).dump();
        return 1;
    }
}
