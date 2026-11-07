#include "encoding.h"

#include <cerrno>
#include <cstring>
#include <iconv.h>

namespace rl {
namespace {

bool ValidUtf8(const std::uint8_t* d, std::size_t n) {
    std::size_t i = 0;
    while (i < n) {
        std::uint8_t c = d[i];
        if (c < 0x80) { ++i; continue; }
        int extra = (c & 0xE0) == 0xC0 ? 1 : (c & 0xF0) == 0xE0 ? 2 : (c & 0xF8) == 0xF0 ? 3 : -1;
        if (extra < 0 || i + extra >= n) return false;
        for (int k = 1; k <= extra; ++k)
            if ((d[i + k] & 0xC0) != 0x80) return false;
        i += extra + 1;
    }
    return true;
}

std::string Iconv(const char* to, const char* from, const char* in, std::size_t inLen) {
    iconv_t cd = iconv_open(to, from);
    if (cd == reinterpret_cast<iconv_t>(-1)) return {};
    std::string out(inLen * 4 + 8, '\0');
    char* src = const_cast<char*>(in);
    std::size_t srcLeft = inLen;
    char* dst = out.data();
    std::size_t dstLeft = out.size();
    iconv(cd, &src, &srcLeft, &dst, &dstLeft);
    out.resize(out.size() - dstLeft);
    iconv_close(cd);
    return out;
}

} // namespace

std::string DecodeAnsiToUtf8(const std::vector<std::uint8_t>& bytes) {
    if (bytes.empty()) return {};
    if (ValidUtf8(bytes.data(), bytes.size())) return std::string(bytes.begin(), bytes.end());
    std::string r = Iconv("UTF-8", "GB18030", reinterpret_cast<const char*>(bytes.data()), bytes.size());
    if (r.empty()) r.assign(bytes.begin(), bytes.end());
    return r;
}

std::vector<std::uint8_t> EncodeUtf8ToAnsi(const std::string& utf8) {
    if (utf8.empty()) return {};
    if (ValidUtf8(reinterpret_cast<const std::uint8_t*>(utf8.data()), utf8.size())) {
        std::string g = Iconv("GB18030", "UTF-8", utf8.data(), utf8.size());
        if (!g.empty()) return std::vector<std::uint8_t>(g.begin(), g.end());
    }
    return std::vector<std::uint8_t>(utf8.begin(), utf8.end());
}

} // namespace rl
