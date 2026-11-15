#ifndef DNS_CACHE_H
#define DNS_CACHE_H
#include "net_compat.h"

#include <ctype.h>
#include <stdbool.h>

#define FNV_OFFSET_32 2166136261U
#define FNV_PRIME_32  16777619U
#define DNS_CACHE_SETS 64  // 64 sets x 2 ways = 128 entries total
#define DNS_CACHE_WAYS 2
#define DNS_DEFAULT_TTL_MS 60000

struct dns_entry {
    uint32_t hash;
    char host[256];
    char port[16];
    struct sockaddr_in addr;
    uint64_t expires_at_ms;
    uint64_t last_used_ms;
    bool valid;
};

struct dns_cache {
    struct dns_entry sets[DNS_CACHE_SETS][DNS_CACHE_WAYS];
};

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

void dns_cache_init(struct dns_cache *cache);

bool dns_cache_lookup(struct dns_cache *cache, const char *host, const char *port, struct sockaddr_in *out_addr);

void dns_cache_insert(struct dns_cache *cache, const char *host, const char *port, const struct sockaddr_in *addr, uint64_t ttl_ms);

#endif