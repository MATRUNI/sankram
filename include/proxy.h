#ifndef PROXY_H
#define PROXY_H
#include <stdint.h>
#include "config.h"
#include "http.h"
#include "url.h"
#include "poll_engine.h"
#include "dns_cache.h"

#define PROXY_DONE   0   // Request completed successfully
#define PROXY_ERROR  1   // Error occurred or client disconnected
#define PROXY_AGAIN  2   // Partial request (EAGAIN); keep session alive!

#define UPSTREAM_POOL_MAX 64
#define UPSTREAM_IDLE_TIMEOUT_MS 10000  // 10 seconds
#define CLIENT_HEADER_TIMEOUT_MS 10000 // 10 seconds total header deadline
#define TUNNEL_BUF_SIZE 8192

struct tunnel_buf {
    char data[TUNNEL_BUF_SIZE];
    size_t len;
    size_t pos;
};
struct tunnel_ctx {
    struct tunnel_buf to_client;
    struct tunnel_buf to_upstream;
};

struct proxy_connection
{
    int client_fd;
    int upstream_fd;
    void *upstream_ssl;
    int status_code;
    size_t body_bytes_sent;
    ssize_t (*read)(struct proxy_connection *conn, void *buf, size_t len);
    ssize_t (*write)(struct proxy_connection *conn, void *buf, size_t len);

    bool is_pooled;
};

struct upstream_pool_entry {
    char host[256];
    char port[16];
    int upstream_fd;
    void *upstream_ssl;
    ssize_t (*read)(struct proxy_connection *conn, void *buf, size_t len);
    ssize_t (*write)(struct proxy_connection *conn, void *buf, size_t len); 
    uint64_t last_used_ms;
};

struct upstream_pool {
    struct upstream_pool_entry entries[UPSTREAM_POOL_MAX];
    int count;
};

typedef enum {
    LEVEL_CLIENT_READ_HEADERS, 
    LEVEL_UPSTREAM_SEND_REQ,   
    
    LEVEL_CLIENT_READ_BODY,    
    LEVEL_UPSTREAM_CONNECT,    
    LEVEL_UPSTREAM_READ_RESP,  

    LEVEL_CLIENT_WRITE_RESP,
    LEVEL_WEBSOCKET_TUNNEL,
    LEVEL_COMPLETE             
} session_level_t;

struct client_session {
    struct proxy_connection con;
    struct poll_engine *engine;
    struct http_url url;
    session_level_t level;
    struct http_request req;
    char *buffer;
    size_t total;
    size_t offset;
    size_t capacity;
    char upstream_host[256];
    char upstream_port[16];
    bool upstream_is_https;
    char initial_buffer[4096];
    struct upstream_pool *pool;
    const struct origin_whitelist *whitelist;

    bool is_websocket;
    struct tunnel_ctx *tunnel;

    uint64_t header_start_ms;
    struct dns_cache *dns_cache;
};

ssize_t plain_read_wrapper(struct proxy_connection *conn, void *buf, size_t len);

ssize_t plain_write_wrapper(struct proxy_connection *conn, void *buf, size_t len);

int conn_write_all(struct proxy_connection *conn, const void *buf, size_t total);

struct client_session *session_create(int client_fd, struct poll_engine *engine);

void session_free(struct client_session *session);

int proxy_handle_client(struct client_session *session);

#endif
