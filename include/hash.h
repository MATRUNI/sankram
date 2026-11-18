#include <ctype.h>
#include "net_compat.h"

#define FNV_OFFSET_32 2166136261U
#define FNV_PRIME_32  16777619U

static inline uint32_t fnv1a_32(const char *str)
{
    uint32_t hash = FNV_OFFSET_32;
    while (*str)
    {
        hash ^= (uint32_t)(unsigned char)tolower((unsigned char)*str++);
        hash *= FNV_PRIME_32;
    }
    return hash;
}
