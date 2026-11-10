# ==============================================================================
# Sankram (संक्रम) — High-Performance C Reverse Proxy & Edge Gateway
# Universal Cross-Platform Makefile (Linux, macOS, BSD, Windows/MinGW)
# ==============================================================================

CC ?= gcc

# ------------------------------------------------------------------------------
# 1. Platform Detection
# ------------------------------------------------------------------------------
ifeq ($(OS),Windows_NT)
    PLATFORM := Windows
else
    UNAME_S := $(shell uname -s 2>/dev/null || echo Unknown)
    ifeq ($(UNAME_S),Darwin)
        PLATFORM := Darwin
    else ifneq ($(filter MINGW% MSYS% CYGWIN%,$(UNAME_S)),)
        PLATFORM := Windows
    else
        PLATFORM := Linux
    endif
endif

# ------------------------------------------------------------------------------
# 2. Target Executables & Platform Extensions
# ------------------------------------------------------------------------------
ifeq ($(PLATFORM),Windows)
    EXE_EXT = .exe
else
    EXE_EXT =
endif

TARGET = build/sankram$(EXE_EXT)
DEBUG_TARGET = build/sankram_debug$(EXE_EXT)
SMALL_TARGET = build/sankram_small$(EXE_EXT)

# ------------------------------------------------------------------------------
# 3. Source File Selection (Common + Native OS Poll Engine & Native SSL)
# ------------------------------------------------------------------------------
# Common core source files across all platforms
COMMON_SRCS = src/config.c src/http.c src/http_error.c src/logger.c \
              src/main.c src/proxy.c src/server.c src/stress.c \
              src/upstream.c src/url.c

# OS-native I/O multiplexer and SSL/TLS engine selection
ifeq ($(PLATFORM),Windows)
    # Native WSAPoll + Windows Native Schannel (Security.h / Schannel.h)
    SRCS = $(COMMON_SRCS) src/poll_wsapoll.c src/tls_schannel.c
else ifeq ($(PLATFORM),Darwin)
    ifeq ($(USE_OPENSSL),1)
        # OpenSSL override
        SRCS = $(COMMON_SRCS) src/poll_kqueue.c src/tls.c
    else
        # Native kqueue + Apple Native Security Framework (SecureTransport)
        SRCS = $(COMMON_SRCS) src/poll_kqueue.c src/tls_darwin.c
    endif
else
    # Native epoll (Linux) + OpenSSL
    SRCS = $(COMMON_SRCS) src/poll_epoll.c src/tls.c
endif

HEADERS = $(wildcard include/*.h)
OBJS = $(patsubst src/%.c, build/obj/%.o, $(SRCS))
DEBUG_OBJS = $(patsubst src/%.c, build/obj_debug/%.o, $(SRCS))
SMALL_OBJS = $(patsubst src/%.c, build/obj_small/%.o, $(SRCS))

# ------------------------------------------------------------------------------
# 4. Compiler & Linker Flags
# ------------------------------------------------------------------------------
INCLUDES = -Iinclude
BASE_CFLAGS = -Wall -Wextra -Werror -std=gnu11 $(INCLUDES)

ifeq ($(PLATFORM),Darwin)
    ifeq ($(USE_OPENSSL),1)
        # macOS with Homebrew OpenSSL
        OPENSSL_DIR := $(shell brew --prefix openssl@3 2>/dev/null || brew --prefix openssl 2>/dev/null || echo /opt/homebrew/opt/openssl)
        CFLAGS ?= -O3 -flto $(BASE_CFLAGS) -I$(OPENSSL_DIR)/include
        DEBUG_CFLAGS = -g -O0 -fsanitize=address,undefined $(BASE_CFLAGS) -I$(OPENSSL_DIR)/include
        SMALL_CFLAGS = -Os -flto -ffunction-sections -fdata-sections $(BASE_CFLAGS) -I$(OPENSSL_DIR)/include
        LDFLAGS = -L$(OPENSSL_DIR)/lib -pthread -lssl -lcrypto
        DEBUG_LDFLAGS = -L$(OPENSSL_DIR)/lib -pthread -lssl -lcrypto -fsanitize=address,undefined
        SMALL_LDFLAGS = $(LDFLAGS) -Wl,-dead_strip
    else
        # macOS Native: Apple Security & CoreFoundation frameworks (Zero external OpenSSL)
        CFLAGS ?= -O3 -flto -Wno-deprecated-declarations $(BASE_CFLAGS)
        DEBUG_CFLAGS = -g -O0 -fsanitize=address,undefined -Wno-deprecated-declarations $(BASE_CFLAGS)
        SMALL_CFLAGS = -Os -flto -ffunction-sections -fdata-sections -Wno-deprecated-declarations $(BASE_CFLAGS)
        LDFLAGS = -framework Security -framework CoreFoundation -pthread
        DEBUG_LDFLAGS = -framework Security -framework CoreFoundation -pthread -fsanitize=address,undefined
        SMALL_LDFLAGS = $(LDFLAGS) -Wl,-dead_strip
    endif

else ifeq ($(PLATFORM),Windows)
    # Windows Native: Winsock2 + Native Schannel + CryptoAPI (Zero external OpenSSL/pthread dependencies)
    CFLAGS ?= -O3 -flto -s -fno-asynchronous-unwind-tables -fno-unwind-tables -fno-ident \
              -ffunction-sections -fdata-sections $(BASE_CFLAGS)
    DEBUG_CFLAGS = -g -O0 $(BASE_CFLAGS)
    SMALL_CFLAGS = -Os -flto -s -fno-asynchronous-unwind-tables -fno-unwind-tables -fno-ident \
                   -ffunction-sections -fdata-sections $(BASE_CFLAGS)
    LDFLAGS = -lws2_32 -lsecur32 -lcrypt32 -Wl,--gc-sections
    DEBUG_LDFLAGS = -lws2_32 -lsecur32 -lcrypt32
    SMALL_LDFLAGS = -lws2_32 -lsecur32 -lcrypt32 -Wl,--gc-sections -s

else
    # Linux / BSD: epoll + OpenSSL
    CFLAGS ?= -O3 -flto -march=native $(BASE_CFLAGS)
    DEBUG_CFLAGS = -g -O0 -fsanitize=address,undefined $(BASE_CFLAGS)
    SMALL_CFLAGS = -Os -flto -march=native -ffunction-sections -fdata-sections $(BASE_CFLAGS)
    LDFLAGS = -pthread -lssl -lcrypto
    DEBUG_LDFLAGS = -pthread -lssl -lcrypto -fsanitize=address,undefined
    SMALL_LDFLAGS = $(LDFLAGS) -Wl,--gc-sections -s
endif

# ------------------------------------------------------------------------------
# 5. Shell & Directory Management Abstraction
# ------------------------------------------------------------------------------
ifeq ($(PLATFORM),Windows)
    ifeq ($(findstring sh,$(SHELL)),)
        # Windows cmd.exe shell
        MKDIR_CMD = if not exist "build\obj" mkdir "build\obj" & if not exist "build\obj_debug" mkdir "build\obj_debug" & if not exist "build\obj_small" mkdir "build\obj_small" & if not exist "logs" mkdir "logs"
        CLEAN_CMD = if exist "build" rmdir /s /q "build" 2>nul & if exist "logs" rmdir /s /q "logs" 2>nul & echo Clean done.
    else
        # Windows with Unix shell (MSYS2, Git Bash, w64devkit)
        MKDIR_CMD = mkdir -p build/obj build/obj_debug build/obj_small logs
        CLEAN_CMD = rm -rf build logs
    endif
else
    # Linux / macOS / BSD
    MKDIR_CMD = mkdir -p build/obj build/obj_debug build/obj_small logs
    CLEAN_CMD = rm -rf build logs
endif

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin

# ------------------------------------------------------------------------------
# 6. Build Targets
# ------------------------------------------------------------------------------
.PHONY: all
all: $(TARGET)

# Production build
$(TARGET): $(OBJS)
	@$(MKDIR_CMD)
	@echo "  [LD]   $@"
	@$(CC) $(CFLAGS) $(OBJS) $(LDFLAGS) -o $@
	@echo "✔ Build complete: $@"

build/obj/%.o: src/%.c $(HEADERS)
	@$(MKDIR_CMD)
	@echo "  [CC]   $<"
	@$(CC) $(CFLAGS) -c $< -o $@

# Debug build
.PHONY: debug
debug: $(DEBUG_TARGET)

$(DEBUG_TARGET): $(DEBUG_OBJS)
	@$(MKDIR_CMD)
	@echo "  [LD]   $@ (debug)"
	@$(CC) $(DEBUG_CFLAGS) $(DEBUG_OBJS) $(DEBUG_LDFLAGS) -o $@
	@echo "✔ Debug build complete: $@"

build/obj_debug/%.o: src/%.c $(HEADERS)
	@$(MKDIR_CMD)
	@echo "  [CC]   $< (debug)"
	@$(CC) $(DEBUG_CFLAGS) -c $< -o $@

# Compact/Embedded size-optimized build (-Os + dead-code elimination + strip)
.PHONY: small
small: $(SMALL_TARGET)

$(SMALL_TARGET): $(SMALL_OBJS)
	@$(MKDIR_CMD)
	@echo "  [LD]   $@ (size-optimized & stripped)"
	@$(CC) $(SMALL_CFLAGS) $(SMALL_OBJS) $(SMALL_LDFLAGS) -o $@
	@echo "✔ Compact build complete: $@"

build/obj_small/%.o: src/%.c $(HEADERS)
	@$(MKDIR_CMD)
	@echo "  [CC]   $< (compact)"
	@$(CC) $(SMALL_CFLAGS) -c $< -o $@

# Run server
.PHONY: run
run: $(TARGET)
	@$(TARGET) -p 17777 -t 8

# Run sanity check
.PHONY: test
test: $(TARGET)
	@echo "Verifying Sankram binary..."
	@$(TARGET) -h
	@echo "✔ Sankram sanity check passed."

# Clean build artifacts
.PHONY: clean
clean:
	@echo "Cleaning build artifacts..."
	@$(CLEAN_CMD)
	@echo "✔ Clean done."

# Global system install (Unix/macOS only)
.PHONY: install
install: $(TARGET)
	@install -d $(DESTDIR)$(BINDIR)
	@install -m 755 $(TARGET) $(DESTDIR)$(BINDIR)/sankram
	@echo "✔ Installed $(TARGET) to $(DESTDIR)$(BINDIR)/sankram"

# Uninstall
.PHONY: uninstall
uninstall:
	@rm -f $(DESTDIR)$(BINDIR)/sankram
	@echo "✔ Removed $(DESTDIR)$(BINDIR)/sankram"
