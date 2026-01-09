# Makefile for hestia-keychain-cli

INSTALL_DIR := $(HOME)/.hestia/bin
BINARY := hestia-keychain-cli

.PHONY: all build release install clean

all: release

build:
	swift build

release:
	swift build -c release

install: release
	@mkdir -p $(INSTALL_DIR)
	@cp .build/release/$(BINARY) $(INSTALL_DIR)/
	@chmod +x $(INSTALL_DIR)/$(BINARY)
	@echo "Installed $(BINARY) to $(INSTALL_DIR)"

clean:
	swift package clean
	rm -rf .build

test:
	@echo "Testing help command..."
	@$(INSTALL_DIR)/$(BINARY) help
	@echo "\nTesting store/retrieve..."
	@echo "test-value" | $(INSTALL_DIR)/$(BINARY) store-credential hestia.test test_key
	@$(INSTALL_DIR)/$(BINARY) retrieve-credential hestia.test test_key
	@$(INSTALL_DIR)/$(BINARY) delete-credential hestia.test test_key
	@echo "\nAll tests passed!"
