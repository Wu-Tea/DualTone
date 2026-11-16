#include "core.hpp"
#include <algorithm>
#include <cmath>

namespace dt {
namespace {
constexpr double MatrixScale = 0.3535533905932737622; // 1 / sqrt(8), unitary Hadamard
constexpr std::array<double, Reverb::Lines> LeftSigns = {1, 1, 1, 1, -1, -1, -1, -1};
constexpr std::array<double, Reverb::Lines> RightSigns = {1, -1, 1, -1, 1, -1, 1, -1};
constexpr double SilenceThreshold = 1e-12;
const double Smooth = 1 - std::exp(-1 / (ProcessingRate * Reverb::ParameterSmoothingSeconds));
const double HighPassPole = std::exp(-2 * std::numbers::pi * Reverb::HighPassHz / ProcessingRate);
} // namespace
Reverb::Reverb() {
    for (size_t i = 0; i < Lines; i++)
        buffers[i].resize(size_t(std::ceil(BaseFrames[i] * MaxSizeScale)) + 2);
}
void Reverb::configure(const json &cfg, bool reset) {
    double size = MinSizeScale + (MaxSizeScale - MinSizeScale) * cfg["reverb_size"].get<double>() / 100;
    double decay = cfg["reverb_decay"];
    double cutoff = MinBrightnessHz * std::pow(MaxBrightnessHz / MinBrightnessHz,
                                               cfg["reverb_brightness"].get<double>() / 100);
    target_damping = std::exp(-2 * std::numbers::pi * cutoff / ProcessingRate);
    flush_frames =
        int((TailFlushMultiples * decay + BaseFrames.back() * size / ProcessingRate) * ProcessingRate);
    for (size_t i = 0; i < Lines; i++) {
        target_delays[i] = BaseFrames[i] * size;
        // Each loop traversal loses 60 dB after the requested low-frequency RT60.
        target_feedback[i] = std::pow(10., -3 * target_delays[i] / (ProcessingRate * decay));
        if (reset) {
            delays[i] = target_delays[i];
            feedback[i] = target_feedback[i];
            std::fill(buffers[i].begin(), buffers[i].end(), 0.);
            positions[i] = 0;
            lowpass[i] = 0;
        }
    }
    if (reset) {
        damping = target_damping;
        hp_input = {};
        hp_output = {};
        remaining = 0;
    }
}
std::array<double, 2> Reverb::tick(double left, double right) {
    if (std::max(std::abs(left), std::abs(right)) > SilenceThreshold)
        remaining = flush_frames;
    else if (remaining) {
        if (!--remaining) {
            // After two nominal RT60 periods, discard inaudible residuals and
            // prevent denormal arithmetic during indefinitely silent streams.
            for (auto &buffer : buffers)
                std::fill(buffer.begin(), buffer.end(), 0.);
            lowpass = {};
            hp_input = {};
            hp_output = {};
            return {};
        }
    } else
        return {};
    std::array<double, 2> input = {left, right};
    for (int ch = 0; ch < 2; ch++) {
        double y = HighPassPole * (hp_output[ch] + input[ch] - hp_input[ch]);
        hp_input[ch] = input[ch];
        hp_output[ch] = y;
        input[ch] = y;
    }
    damping += Smooth * (target_damping - damping);
    std::array<double, Lines> mixed{};
    std::array<double, 2> output{};
    for (size_t i = 0; i < Lines; i++) {
        delays[i] += Smooth * (target_delays[i] - delays[i]);
        feedback[i] += Smooth * (target_feedback[i] - feedback[i]);
        double read = double(positions[i]) - delays[i];
        if (read < 0)
            read += buffers[i].size();
        size_t index = size_t(read);
        double fraction = read - index;
        double delayed =
            buffers[i][index] * (1 - fraction) + buffers[i][(index + 1) % buffers[i].size()] * fraction;
        lowpass[i] = (1 - damping) * delayed + damping * lowpass[i];
        mixed[i] = lowpass[i] * feedback[i];
        output[0] += LeftSigns[i] * lowpass[i] * MatrixScale;
        output[1] += RightSigns[i] * lowpass[i] * MatrixScale;
    }
    // Fast normalized Walsh-Hadamard mixing: preserves feedback energy.
    for (size_t width = 1; width < Lines; width *= 2)
        for (size_t base = 0; base < Lines; base += 2 * width)
            for (size_t j = 0; j < width; j++) {
                double a = mixed[base + j], b = mixed[base + j + width];
                mixed[base + j] = a + b;
                mixed[base + j + width] = a - b;
            }
    for (size_t i = 0; i < Lines; i++) {
        double injection = (LeftSigns[i] * input[0] + RightSigns[i] * input[1]) * MatrixScale;
        // Keep broadband energy similar when the decay changes.
        injection *= std::sqrt(1 - feedback[i] * feedback[i]);
        buffers[i][positions[i]] = mixed[i] * MatrixScale + injection;
        positions[i] = (positions[i] + 1) % buffers[i].size();
    }
    // Bound wet-only transients before the existing output gain/headroom stage.
    return {std::tanh(output[0]), std::tanh(output[1])};
}
} // namespace dt
