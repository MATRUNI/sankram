#ifndef MEMI_H
#define MEMI_H

enum memi_hash {
    // Web Core
    HASH_HTML   = 0xD775A7D0U,
    HASH_HTM    = 0x078FDA9CU,
    HASH_CSS    = 0xF3471E80U,
    HASH_JS     = 0x5E3F640AU,
    HASH_MJS    = 0xD491953FU,
    HASH_JSON   = 0x36A1A243U,
    HASH_WASM   = 0xA5F6CD4DU,
    HASH_TXT    = 0xA535A9EFU,
    HASH_XML    = 0xDA706EB6U,

    // Images
    HASH_SVG    = 0xE7478EA1U,
    HASH_PNG    = 0x6835C29CU,
    HASH_JPG    = 0xDAC75F30U,
    HASH_JPEG   = 0xBEDF9323U,
    HASH_GIF    = 0x662AD8C1U,
    HASH_WEBP   = 0xD4C45633U,
    HASH_AVIF   = 0xD793CA19U,
    HASH_ICO    = 0x7CE1083EU,

    // Fonts
    HASH_WOFF2  = 0x07A54453U,
    HASH_WOFF   = 0x58CA6A73U,
    HASH_TTF    = 0xB72B38E9U,
    HASH_OTF    = 0xCB182A28U,

    // Media & Docs
    HASH_MP4    = 0x9D7939C4U,
    HASH_WEBM   = 0xEFC480B4U,
    HASH_MP3    = 0x9C793831U,
    HASH_PDF    = 0x694DC915U
};

const char *get_memi_type(const char *path);

#endif