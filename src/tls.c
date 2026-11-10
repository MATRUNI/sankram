#if !defined(_WIN32)
#include <openssl/ssl.h>

#include "proxy.h"
#include "tls.h"
#include "logger.h"
#include "net_compat.h"

static SSL_CTX *global_ssl_ctx = NULL;

int tls_init(void)
{
    if(global_ssl_ctx!=NULL) return 0;

    global_ssl_ctx = SSL_CTX_new(TLS_client_method());

    if(global_ssl_ctx==NULL) return 1;

    SSL_CTX_set_default_verify_paths(global_ssl_ctx);
    return 0;
}

void tls_cleanup(void)
{
    if(global_ssl_ctx!=NULL)
    {
        SSL_CTX_free(global_ssl_ctx);
        global_ssl_ctx=NULL;
    }
}

static ssize_t ssl_write_wrapper(struct proxy_connection *conn, void *buf, size_t len)
{
    return SSL_write((SSL *)conn->upstream_ssl,buf,len);
}

static ssize_t ssl_read_wrapper(struct proxy_connection *conn, void *buf, size_t len)
{
    return SSL_read((SSL *)conn->upstream_ssl,buf,len);
}

int tls_connect(struct proxy_connection *conn, const char *hostname)
{
    SSL *ssl = SSL_new(global_ssl_ctx);
    if(ssl==NULL) return 1;
    SSL_set_fd(ssl,conn->upstream_fd);
    SSL_set_tlsext_host_name(ssl,hostname);
    if(SSL_connect(ssl)<=0)
    {
        SSL_free(ssl);
        return 1;
    }
    conn->upstream_ssl = ssl;
    conn->read = ssl_read_wrapper;
    conn->write = ssl_write_wrapper;
    return 0;
}

void conn_close(struct proxy_connection *conn)
{
    if(conn==NULL) return;
    if(conn->upstream_ssl!=NULL)
    {
        SSL_shutdown((SSL *)conn->upstream_ssl);
        SSL_free((SSL *)conn->upstream_ssl);
        conn->upstream_ssl=NULL;
    }
    if(conn->upstream_fd>=0)
    {
        close_socket(conn->upstream_fd);
        conn->upstream_fd=-1;
    }
}
#endif