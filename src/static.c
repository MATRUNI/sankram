#include <stddef.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#if defined (__linux__)
    #include <sys/sendfile.h>
#endif

#include "memi.h"
#include "net_compat.h"
#include "static.h"

static int build_safe_path(char *out, size_t out_len, const char *root_dir, const char *url_path)
{
    if (out == NULL || root_dir == NULL || url_path == NULL || out_len == 0)
        return 1;
    size_t path_len = 0;
    size_t root_len = strlen(root_dir);
    while (root_len > 0 && (root_dir[root_len - 1] == '/' || root_dir[root_len - 1] == '\\')) {
        root_len--;
    }
    if (url_path[0] == '.') return 1;
    for(size_t i = 0; url_path[i]!='\0'; i++)
    {
        if(url_path[i] == '.' && url_path[i+1]=='.') return 1;
        else if(url_path[i] == '/' && url_path[i+1] == '.') return 1;
        else if (url_path[i] == '?')
        {
            path_len = i;
            break;
        }
        path_len = i + 1;
    }
    if (path_len == 1 && url_path[0] == '/') {
        snprintf(out, out_len, "%.*s/index.html", (int)root_len ,root_dir);
    }
    else if (path_len > 1 && url_path[path_len - 1] == '/') {
        snprintf(out, out_len, "%.*s%.*sindex.html", (int)root_len, root_dir, (int)path_len, url_path);
    }
    else {
        snprintf(out, out_len, "%.*s%.*s", (int)root_len, root_dir, (int)path_len, url_path);
    }
    return 0;
}

static int send_file_response(int client_fd, const char *file_path, size_t file_size)
{
    int fd = open(file_path, O_RDONLY);
    if(fd<0) return 1;

    const char *mime = get_memi_type(file_path);
    char header[256];
    int hlen = snprintf(header, sizeof(header),
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: %s\r\n"
        "Content-Length: %zu\r\n"
        "Connection: keep-alive\r\n"
        "Server: Sankram\r\n\r\n",
        mime, file_size);

    if (hlen > 0) {
        send(client_fd, header, hlen, 0);
    }
    #if defined(__linux__)
        off_t offset = 0;
        while (offset < (off_t)file_size) {
            ssize_t sent = sendfile(client_fd, fd, &offset, file_size - offset);
            if (sent <= 0) break;
        }
    #else
        char buf[8192];
        ssize_t n;
        while ((n = read(fd, buf, sizeof(buf))) > 0) {
            send(client_fd, buf, n, 0);
        }
    #endif
    close(fd);
    return 0;
}

int serve_static_file(int client_fd, const char *root_dir, const char *url_path, bool spa_mode)
{
    char file_path[128];
    if(build_safe_path(file_path,sizeof(file_path),root_dir,url_path)==1) return 1;
    struct stat st;
    if(stat(file_path,&st)!=0)
    {
        if(spa_mode)
        {
            build_safe_path(file_path, sizeof(file_path), root_dir, "/index.html");
            if(stat(file_path,&st)!=0) return -1;
            
            return send_file_response(client_fd,file_path,st.st_size);
        }
        else return -1;
    }
    if(send_file_response(client_fd,file_path,st.st_size)==1) return 1;
    return 0;
}