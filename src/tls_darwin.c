#if defined(__APPLE__)
#include <Security/Security.h>
#include <Security/SecureTransport.h>
#include <CoreFoundation/CoreFoundation.h>
#include <sys/socket.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <poll.h>
#include "tls.h"
#include "proxy.h"
#include "logger.h"
#include "net_compat.h"

struct darwin_tls_session {
    SSLContextRef ssl;
    int fd;
};

int tls_init(void)
{
    // Apple Security framework requires no global state init
    return 0;
}

void tls_cleanup(void)
{
    // No global context teardown required
}

static OSStatus darwin_ssl_read(SSLConnectionRef connection, void *data, size_t *dataLength)
{
    struct darwin_tls_session *sess = (struct darwin_tls_session *)connection;
    size_t requested = *dataLength;
    if (requested == 0) return noErr;

    ssize_t n = recv(sess->fd, data, requested, 0);
    if (n > 0) {
        *dataLength = (size_t)n;
        if ((size_t)n < requested) {
            return errSSLWouldBlock;
        }
        return noErr;
    }

    *dataLength = 0;
    if (n == 0) {
        return errSSLClosedGraceful;
    }

    int err = errno;
    if (err == EAGAIN || err == EWOULDBLOCK) {
        return errSSLWouldBlock;
    }
    return errSecIO;
}

static OSStatus darwin_ssl_write(SSLConnectionRef connection, const void *data, size_t *dataLength)
{
    struct darwin_tls_session *sess = (struct darwin_tls_session *)connection;
    size_t requested = *dataLength;
    if (requested == 0) return noErr;

    ssize_t n = send(sess->fd, data, requested, 0);
    if (n > 0) {
        *dataLength = (size_t)n;
        if ((size_t)n < requested) {
            return errSSLWouldBlock;
        }
        return noErr;
    }

    *dataLength = 0;
    int err = errno;
    if (n < 0 && (err == EAGAIN || err == EWOULDBLOCK)) {
        return errSSLWouldBlock;
    }
    return errSecIO;
}

static ssize_t darwin_ssl_read_wrapper(struct proxy_connection *conn, void *buf, size_t len)
{
    struct darwin_tls_session *sess = (struct darwin_tls_session *)conn->upstream_ssl;
    size_t processed = 0;
    OSStatus status;

    while (1) {
        status = SSLRead(sess->ssl, buf, len, &processed);
        if (processed > 0) {
            return (ssize_t)processed;
        }
        if (status == errSSLWouldBlock) {
            struct pollfd pfd = { .fd = sess->fd, .events = POLLIN, .revents = 0 };
            int pr = poll(&pfd, 1, 10000);
            if (pr > 0 && (pfd.revents & (POLLIN | POLLHUP | POLLERR))) {
                continue;
            }
            if (pr == 0) {
                errno = EAGAIN;
                return -1;
            }
            errno = EIO;
            return -1;
        }
        break;
    }

    if (status == errSSLClosedGraceful || status == errSSLClosedNoNotify || (status == noErr && processed == 0)) {
        return 0;
    }
    errno = EIO;
    return -1;
}

static ssize_t darwin_ssl_write_wrapper(struct proxy_connection *conn, void *buf, size_t len)
{
    struct darwin_tls_session *sess = (struct darwin_tls_session *)conn->upstream_ssl;
    size_t processed = 0;
    OSStatus status;

    while (1) {
        status = SSLWrite(sess->ssl, buf, len, &processed);
        if (processed > 0) {
            return (ssize_t)processed;
        }
        if (status == errSSLWouldBlock) {
            struct pollfd pfd = { .fd = sess->fd, .events = POLLOUT, .revents = 0 };
            int pr = poll(&pfd, 1, 10000);
            if (pr > 0 && (pfd.revents & POLLOUT)) {
                continue;
            }
            if (pr == 0) {
                errno = EAGAIN;
                return -1;
            }
            errno = EIO;
            return -1;
        }
        break;
    }

    errno = EIO;
    return -1;
}

int tls_connect(struct proxy_connection *conn, const char *hostname)
{
    struct darwin_tls_session *sess = calloc(1, sizeof(struct darwin_tls_session));
    if (sess == NULL) return 1;

    SSLContextRef ssl = SSLCreateContext(kCFAllocatorDefault, kSSLClientSide, kSSLStreamType);
    if (ssl == NULL) {
        free(sess);
        return 1;
    }

    sess->ssl = ssl;
    sess->fd = conn->upstream_fd;
    conn->upstream_ssl = sess;

#if defined(SO_NOSIGPIPE)
    int val = 1;
    setsockopt(sess->fd, SOL_SOCKET, SO_NOSIGPIPE, &val, sizeof(val));
#endif

    OSStatus status = SSLSetIOFuncs(ssl, darwin_ssl_read, darwin_ssl_write);
    if (status != noErr) {
        CFRelease(ssl);
        free(sess);
        conn->upstream_ssl = NULL;
        return 1;
    }

    status = SSLSetConnection(ssl, (SSLConnectionRef)sess);
    if (status != noErr) {
        CFRelease(ssl);
        free(sess);
        conn->upstream_ssl = NULL;
        return 1;
    }

    if (hostname != NULL && strlen(hostname) > 0) {
        status = SSLSetPeerDomainName(ssl, hostname, strlen(hostname));
        if (status != noErr) {
            CFRelease(ssl);
            free(sess);
            conn->upstream_ssl = NULL;
            return 1;
        }
    }

    status = SSLSetProtocolVersionMin(ssl, kTLSProtocol12);
    if (status != noErr) {
        CFRelease(ssl);
        free(sess);
        conn->upstream_ssl = NULL;
        return 1;
    }
    status = SSLSetProtocolVersionMax(ssl, kTLSProtocol12);
    if (status != noErr) {
        CFRelease(ssl);
        free(sess);
        conn->upstream_ssl = NULL;
        return 1;
    }

    do {
        status = SSLHandshake(ssl);
        if (status == errSSLWouldBlock) {
            struct pollfd pfd = { .fd = sess->fd, .events = POLLIN | POLLOUT, .revents = 0 };
            if (poll(&pfd, 1, 10000) <= 0) {
                status = errSecIO;
                break;
            }
        }
    } while (status == errSSLWouldBlock);

    if (status != noErr) {
        CFRelease(ssl);
        free(sess);
        conn->upstream_ssl = NULL;
        return 1;
    }

    conn->read = darwin_ssl_read_wrapper;
    conn->write = darwin_ssl_write_wrapper;
    return 0;
}

void conn_close(struct proxy_connection *conn)
{
    if (conn == NULL) return;
    if (conn->upstream_ssl != NULL) {
        struct darwin_tls_session *sess = (struct darwin_tls_session *)conn->upstream_ssl;
        SSLClose(sess->ssl);
        CFRelease(sess->ssl);
        free(sess);
        conn->upstream_ssl = NULL;
    }
    if (conn->upstream_fd >= 0) {
        close_socket(conn->upstream_fd);
        conn->upstream_fd = -1;
    }
    conn->read = NULL;
    conn->write = NULL;
}

#endif
