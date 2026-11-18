#include "hash.h"
#include "memi.h"
#include <string.h>
const char *get_memi_type(const char *path)
{
    if(path==NULL) goto return_default;
    const char *dot = strrchr(path,'.');
    if(dot==NULL || dot[1]=='\0') goto return_default;
    uint32_t hash = fnv1a_32(dot+1);
    switch (hash)
    {
        case HASH_HTML: 
        case HASH_HTM: 
            return "text/html; charset=utf-8";
        case HASH_CSS: 
            return "text/css; charset=utf-8";
        case HASH_JS: 
        case HASH_MJS: 
            return "application/javascript; charset=utf-8";
        case HASH_JSON: 
            return "application/json; charset=utf-8";
        case HASH_SVG: 
            return "image/svg+xml";
        case HASH_PNG: 
            return "image/png";
        case HASH_JPG: 
        case HASH_JPEG: 
            return "image/jpeg";
        case HASH_WEBP: 
            return "image/webp";
        case HASH_AVIF: 
            return "image/avif";
        case HASH_ICO: 
            return "image/x-icon";
        case HASH_WOFF2: 
            return "font/woff2";
        case HASH_WOFF: 
            return "font/woff";
        case HASH_TTF: 
            return "font/ttf";
        case HASH_WASM: 
            return "application/wasm";
        default:
            goto return_default;
    }
    return_default:
    return "application/octet-stream";
}
