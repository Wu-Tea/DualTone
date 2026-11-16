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
        } else if (command == "render") {
            auto cfg = validate(input.at("settings"));
            Processor p; p.update(std::make_shared<Dsp>(cfg));
            std::vector<double> rendered;
            uint32_t random=104729;
            for (auto &segment : input.at("segments")) {
                if (segment.contains("patch")) {
                    cfg=merge(cfg,segment["patch"]);
                    p.update(std::make_shared<Dsp>(cfg));
                }
                int frames=segment.at("frames"),chunk=segment.value("chunk",480);
                std::string signal=segment.value("signal","silence");
                for (int offset=0;offset<frames;offset+=chunk) {
                    std::vector<double> packet(std::min(chunk,frames-offset)*2);
                    for (size_t i=0;i<packet.size();i++) {
                        if (signal=="impulse" && offset==0 && i==0) packet[i]=.25;
                        if (signal=="noise") {
                            random=random*1664525u+1013904223u;
                            packet[i]=(double(random)/UINT32_MAX-.5)*.5;
                        }
                    }
                    p.process(packet,segment.value("paused",false));
                    rendered.insert(rendered.end(),packet.begin(),packet.end());
                }
            }
            if (input.value("samples",false)) output["samples"]=rendered;
            double peak=0;int first=-1;
            json energies=json::array();
            constexpr size_t WindowFrames=ProcessingRate/10;
            for (size_t block=0;block<rendered.size()/2;block+=WindowFrames) {
                double left=0,right=0;
                for (size_t f=block;f<std::min(block+WindowFrames,rendered.size()/2);f++) {
                    left+=rendered[f*2]*rendered[f*2];right+=rendered[f*2+1]*rendered[f*2+1];
                    for (int c=0;c<2;c++) {
                        double value=rendered[f*2+c];
                        if (!std::isfinite(value)) throw std::runtime_error("non-finite DSP output");
                        peak=std::max(peak,std::abs(value));
                        if (first<0 && std::abs(value)>1e-12) first=int(f);
                    }
                }
                energies.push_back({left,right});
            }
            output["energy_100ms"]=energies;output["first_frame"]=first;output["peak"]=peak;
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
