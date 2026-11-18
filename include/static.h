#ifndef STATIC_H
#define STATIC_H
#include <stdbool.h>

int serve_static_file(int client_fd, const char *root_dir, const char *url_path, bool spa_mode);

#endif