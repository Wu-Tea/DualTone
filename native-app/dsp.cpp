#include "core.hpp"
#include "resampler_tables.hpp"
#include <algorithm>
#include <numeric>
namespace dt {
constexpr double Pi = std::numbers::pi;
double Biquad::tick(double x, int c) {
    double y = b0 * x + z1[c];
    z1[c] = b1 * x - a1 * y + z2[c];
    z2[c] = b2 * x - a2 * y;
    return y;
}
Complex Biquad::response(double f) const {
    auto z = std::polar(1., -2 * Pi * f / ProcessingRate);
    return (b0 + b1 * z + b2 * z * z) / (1. + a1 * z + a2 * z * z);
}
Complex response(const Sections &rows, double f) {
    Complex h = 1;
    for (auto &s : rows)
        h *= s.response(f);
    return h;
}
static Sections peaks(const std::array<double, 10> &g) {
    Sections rows;
    for (int i = 0; i < 10; i++) {
        double w = 2 * Pi * EqFrequencies[i] / ProcessingRate, a = pow(10., g[i] / 40),
               alpha = sin(w) / (2 * EqQ), norm = 1 + alpha / a;
        rows.push_back({(1 + alpha * a) / norm, -2 * cos(w) / norm, (1 - alpha * a) / norm,
                        -2 * cos(w) / norm, (1 - alpha / a) / norm});
    }
    return rows;
}
static std::array<double, 10> curve(const std::array<double, 10> &g) {
    auto sos = peaks(g);
    std::array<double, 10> r;
    for (int i = 0; i < 10; i++)
        r[i] = 20 * log10(abs(response(sos, EqFrequencies[i])));
    return r;
}
Sections make_eq(const json &gains) {
    std::array<double, 10> g{}, goal{};
    for (int i = 0; i < 10; i++)
        g[i] = goal[i] = gains[i];
    constexpr double DerivativeStepDb = .001, FitToleranceDb = .001, CoefficientBoundDb = 30;
    for (int iteration = 0; iteration < 40; iteration++) {
        auto r = curve(g);
        double err = 0;
        for (int i = 0; i < 10; i++)
            err = std::max(err, abs(r[i] - goal[i]));
        if (err < FitToleranceDb)
            return peaks(g);
        double a[10][11]{};
        for (int j = 0; j < 10; j++) {
            auto t = g;
            t[j] += DerivativeStepDb;
            auto d = curve(t);
            for (int i = 0; i < 10; i++)
                a[i][j] = (d[i] - r[i]) / DerivativeStepDb;
        }
        for (int i = 0; i < 10; i++)
            a[i][10] = goal[i] - r[i];
        for (int j = 0; j < 10; j++) {
            int p = j;
            for (int i = j + 1; i < 10; i++)
                if (abs(a[i][j]) > abs(a[p][j]))
                    p = i;
            for (int k = j; k <= 10; k++)
                std::swap(a[p][k], a[j][k]);
            if (abs(a[j][j]) < 1e-10)
                throw std::runtime_error("EQ 拟合矩阵退化");
            double norm = a[j][j];
            for (int k = j; k <= 10; k++)
                a[j][k] /= norm;
            for (int i = 0; i < 10; i++)
                if (i != j) {
                    double n = a[i][j];
                    for (int k = j; k <= 10; k++)
                        a[i][k] -= n * a[j][k];
                }
        }
        bool improved = false;
        for (double step = 1; step >= 1. / 128; step /= 2) {
            auto t = g;
            for (int i = 0; i < 10; i++)
                t[i] = std::clamp(g[i] + step * a[i][10], -CoefficientBoundDb, CoefficientBoundDb);
            auto q = curve(t);
            double e = 0;
            for (int i = 0; i < 10; i++)
                e = std::max(e, abs(q[i] - goal[i]));
            if (e < err) {
                g = t;
                improved = true;
                break;
            }
        }
        if (!improved)
            break;
    }
    auto h = curve(g);
    for (int i = 0; i < 10; i++)
        if (abs(h[i] - goal[i]) > .15)
            throw std::runtime_error("无法准确生成 EQ 曲线");
    return peaks(g);
}
Sections make_band(double low, double high) {
    double fs2 = 2. * ProcessingRate, lo = fs2 * tan(Pi * low / ProcessingRate),
           hi = fs2 * tan(Pi * high / ProcessingRate), bw = hi - lo, center = sqrt(lo * hi);
    std::vector<Complex> poles;
    for (int k = 0; k < 3; k++) {
        Complex p = std::polar(1., Pi * (2 * k + 4) / 6) * bw / 2.;
        auto q = sqrt(p * p - center * center);
        for (auto s : {p + q, p - q})
            poles.push_back((fs2 + s) / (fs2 - s));
    }
    Sections result;
    for (auto p : poles)
        if (p.imag() > 1e-10)
            result.push_back({1, 0, -1, -2 * p.real(), std::norm(p)});
    // If a narrow/wide transform creates real poles, pair the remaining real roots.
    std::vector<double> real;
    for (auto p : poles)
        if (abs(p.imag()) <= 1e-10)
            real.push_back(p.real());
    for (size_t i = 0; i + 1 < real.size(); i += 2)
        result.push_back({1, 0, -1, -real[i] - real[i + 1], real[i] * real[i + 1]});
    if (result.size() != 3)
        throw std::runtime_error("带通极点配对失败");
    double hz = ProcessingRate / Pi * atan(center / fs2), scale = 1. / abs(response(result, hz));
    result[0].b0 *= scale;
    result[0].b2 *= scale;
    return result;
}
Dsp::Dsp(json settings) : cfg(validate(settings)), eq(make_eq(cfg["gains"])) {
    if (cfg["band_enabled"].get<bool>())
        for (auto &b : cfg["bands"])
            if (b["enabled"].get<bool>())
                bands.push_back(
                    {make_band(b["low"], b["high"]), pow(10., b["gain_db"].get<double>() / 20)});
    double peak = 0;
    auto scan = [&](double f) {
        peak = std::max(
            peak, abs((cfg["eq_enabled"].get<bool>() ? eq_response(f) : Complex(1)) * band_response(f)));
    };
    for (int i = 0; i < 12000; i++)
        scan(20 * pow(1000., double(i) / 11999));
    for (auto &b : cfg["bands"])
        if (cfg["band_enabled"].get<bool>() && b["enabled"].get<bool>())
            for (int i = 0; i < 65; i++)
                scan(b["low"].get<double>() +
                     (b["high"].get<double>() - b["low"].get<double>()) * i / 64);
    preamp_db = -std::max(0., 20 * log10(std::max(peak, 1e-12))) - HeadroomDb;
}
Complex Dsp::eq_response(double hz) const {
    return response(eq, hz);
}
Complex Dsp::band_response(double hz) const {
    if (!cfg["band_enabled"].get<bool>())
        return 1.;
    Complex sum = 0;
    for (auto &[s, g] : bands)
        sum += response(s, hz) * g;
    return sum;
}
void Processor::update(std::shared_ptr<Dsp> d) {
    if (d == current)
        return;
    if (!current || d->cfg["gains"] != current->cfg["gains"])
        eq = d->eq;
    if (!current || d->cfg["bands"] != current->cfg["bands"] ||
        d->cfg["band_enabled"] != current->cfg["band_enabled"])
        bands = d->bands;
    target_mid = pow(10., -MidCutDb * d->cfg["spatial_strength"].get<double>() / 100 / 20);
    if (!current) {
        mid = target_mid;
        ramp = 0;
    } else {
        ramp = SpatialRampFrames;
        mid_step = (target_mid - mid) / ramp;
    }
    current = d;
}
void Processor::process(std::vector<double> &packet, bool paused) {
    auto &cfg = current->cfg;
    bool band = cfg["band_enabled"], eq_on = cfg["eq_enabled"];
    double gain = paused ? 0 : cfg["gain"].get<double>() / 100 * pow(10., current->preamp_db / 20);
    for (size_t i = 0; i < packet.size(); i += 2) {
        double v[2];
        for (int ch = 0; ch < 2; ch++) {
            double x = packet[i + ch];
            v[ch] = band ? 0 : x;
            if (band)
                for (auto &[s, g] : bands) {
                    double t = x;
                    for (auto &b : s)
                        t = b.tick(t, ch);
                    v[ch] += t * g;
                }
            double t = v[ch];
            for (auto &b : eq)
                t = b.tick(t, ch);
            if (eq_on)
                v[ch] = t;
        }
        if (ramp) {
            mid += mid_step;
            if (!--ramp)
                mid = target_mid;
        }
        double m = (v[0] + v[1]) * .5 * (1 - mid);
        packet[i] = (v[0] - m) * gain;
        packet[i + 1] = (v[1] - m) * gain;
    }
}
Resampler::Resampler(int source, int target) {
    if (source == target)
        return;
    for (auto &r : resample_tables)
        if (r.source == source && r.target == target) {
            up = r.up;
            down = r.down;
            taps = r.taps;
            taps_size = r.count;
            return;
        }
    throw std::runtime_error("不支持的重采样组合");
}
std::vector<double> Resampler::process(const std::vector<double> &p) {
    if (up == down)
        return p;
    size_t count = p.size() / 2;
    std::vector<double> data = history;
    data.insert(data.end(), p.begin(), p.end());
    int64_t total = inputs + count, newout = (total * up + down - 1) / down;
    std::vector<double> result((newout - outputs) * 2);
    for (int64_t n = outputs; n < newout; n++) {
        int64_t phase = n * down, last = phase / up,
                first = std::max<int64_t>(origin, (phase - int64_t(taps_size) + up) / up);
        for (int64_t k = first; k <= last && k < total; k++) {
            auto t = phase - k * up;
            if (t < 0 || t >= int64_t(taps_size))
                continue;
            for (int c = 0; c < 2; c++)
                result[(n - outputs) * 2 + c] += taps[t] * data[(k - origin) * 2 + c];
        }
    }
    int64_t memory = (taps_size + up - 2) / up,
            neworigin = std::max<int64_t>(0, (total - memory) / down * down);
    history.assign(data.begin() + (neworigin - origin) * 2, data.end());
    origin = neworigin;
    inputs = total;
    outputs = newout;
    return result;
}
void fft(std::vector<Complex> &a, bool inverse) {
    size_t n = a.size();
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1)
            j ^= bit;
        j ^= bit;
        if (i < j)
            std::swap(a[i], a[j]);
    }
    for (size_t len = 2; len <= n; len *= 2) {
        auto wl = std::polar(1., (inverse ? 2 : -2) * Pi / len);
        for (size_t i = 0; i < n; i += len) {
            Complex w = 1;
            for (size_t j = 0; j < len / 2; j++) {
                auto u = a[i + j], v = a[i + j + len / 2] * w;
                a[i + j] = u + v;
                a[i + j + len / 2] = u - v;
                w *= wl;
            }
        }
    }
    if (inverse)
        for (auto &x : a)
            x /= double(n);
}
} // namespace dt
