#include "core.hpp"
#include <algorithm>
#include <cmath>
namespace dt {
MainDelay::MainDelay(double ms)
    : ring(size_t(MaxMainDelayMs * ProcessingRate / 1000) + 2),
      delay(ms * ProcessingRate / 1000), previous(delay), requested(delay) {}
void MainDelay::process(std::vector<double> &samples, double ms) {
    requested = ms * ProcessingRate / 1000;
    for (size_t i = 0; i < samples.size(); i += 2) {
        if (!transition && requested != delay) {
            previous = delay;
            delay = requested;
            transition = DelayTransitionFrames;
        }
        ring[position] = {samples[i], samples[i + 1]};
        auto read = [&](double offset, int ch) {
            size_t whole = size_t(offset);
            double fraction = offset - whole;
            size_t a = (position + ring.size() - whole) % ring.size();
            size_t b = (a + ring.size() - 1) % ring.size();
            return ring[a][ch] * (1 - fraction) + ring[b][ch] * fraction;
        };
        double blend = transition ? 1. - double(transition) / DelayTransitionFrames : 1.;
        for (int ch = 0; ch < 2; ++ch)
            samples[i + ch] = read(previous, ch) * (1 - blend) + read(delay, ch) * blend;
        if (transition) --transition;
        position = (position + 1) % ring.size();
    }
}
void ClockQueue::push(const std::vector<double> &samples) {
    if ((frames.size() + samples.size() / 2) * 1000. / rate > SyncQueueLimitMs)
        throw std::runtime_error("同步输出积压超过 250 ms，请检查设备连接后重新启动");
    for (size_t i = 0; i < samples.size(); i += 2)
        frames.push_back({samples[i], samples[i + 1]});
}
std::vector<double> ClockQueue::pull(size_t count) {
    std::vector<double> out(count * 2);
    if (!primed) {
        if (frames.size() < size_t(rate * SyncQueueMs / 1000) + count) return out;
        primed = true;
    }
    // Queue occupancy at render events varies by one packet. Low-pass it before
    // applying a small clock-rate correction; never accumulate device drift.
    double desired = rate * SyncQueueMs / 1000 + count;
    double alpha = 1 - std::exp(-double(count) / rate / SyncClockTimeSeconds);
    error += alpha * ((double(frames.size()) - desired) / rate - error);
    correction = std::clamp(error / SyncClockTimeSeconds, -SyncMaxClockCorrection, SyncMaxClockCorrection);
    double step = 1 + correction;
    for (size_t i = 0; i < count; ++i) {
        if (size_t(position) + 1 >= frames.size()) {
            ++underruns;
            primed = false;
            // An actual starvation boundary: discard the interpolation history,
            // output silence and refill the bounded jitter buffer.
            frames.clear(); position = 0; error = correction = 0;
            break;
        }
        auto a = size_t(position);
        double t = position - a;
        for (int ch = 0; ch < 2; ++ch)
            out[i * 2 + ch] = frames[a][ch] * (1 - t) + frames[a + 1][ch] * t;
        position += step;
    }
    auto consumed = std::min(size_t(position), frames.size());
    for (size_t i = 0; i < consumed; ++i) frames.pop_front();
    position -= consumed;
    return out;
}
} // namespace dt
