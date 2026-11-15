#include "dns_cache.h"
#include <string.h>
#include <strings.h>

void dns_cache_init(struct dns_cache *cache)
{
    if (cache != NULL) {
        memset(cache, 0, sizeof(*cache));
    }
}

bool dns_cache_lookup(struct dns_cache *cache, const char *host, const char *port, struct sockaddr_in *out_addr)
{
    if(cache == NULL || host == NULL || port == NULL || out_addr == NULL) return false;
    uint32_t hash = fnv1a_32(host);
    int set_idx = hash & (DNS_CACHE_SETS - 1);
    uint64_t now = get_time_ms();

    for(int way = 0; way < 2; way++)
    {
        struct dns_entry *entry = &cache->sets[set_idx][way];
        
        if (!entry->valid || now > entry->expires_at_ms) continue;
        
        if (entry->hash == hash)
        {
            if (strcasecmp(entry->host, host) == 0 && strcmp(entry->port, port) == 0)
            {
                entry->last_used_ms = now;
                *out_addr = entry->addr;
                return true;
            }
        }
    }
    return false;
}

void dns_cache_insert(struct dns_cache *cache, const char *host, const char *port, const struct sockaddr_in *addr, uint64_t ttl_ms)
{
    if(cache == NULL || host == NULL || port == NULL || addr == NULL) return;
    uint32_t hash = fnv1a_32(host);
    int set_idx = hash & (DNS_CACHE_SETS - 1);
    uint64_t now = get_time_ms();
    struct dns_entry *e0 = &cache->sets[set_idx][0];
    struct dns_entry *e1 = &cache->sets[set_idx][1];
    struct dns_entry *entry;

    if (!e0->valid)
        entry = e0;
    else if (!e1->valid)
        entry = e1;
    else if (now > e0->expires_at_ms)
        entry = e0;
    else if (now > e1->expires_at_ms)
        entry = e1;
    else
        entry = (e0->last_used_ms <= e1->last_used_ms) ? e0 : e1;
    
    entry->hash = hash;
    strncpy(entry->host, host, sizeof(entry->host) - 1);
    entry->host[sizeof(entry->host) - 1] = '\0';
    strncpy(entry->port, port, sizeof(entry->port) - 1);
    entry->port[sizeof(entry->port) - 1] = '\0';
    entry->expires_at_ms = now + (ttl_ms > 0 ? ttl_ms : DNS_DEFAULT_TTL_MS);
    entry->last_used_ms = now;
    entry->valid = true;
    entry->addr = *addr;
}