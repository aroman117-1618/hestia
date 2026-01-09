.PHONY: build release install clean test

INSTALL_DIR := $(HOME)/.hestia/bin
BINARY_NAME := hestia-reminders-cli

build:
	swift build

release:
	swift build -c release

install: release
	mkdir -p $(INSTALL_DIR)
	cp .build/release/$(BINARY_NAME) $(INSTALL_DIR)/
	chmod +x $(INSTALL_DIR)/$(BINARY_NAME)
	@echo "Installed $(BINARY_NAME) to $(INSTALL_DIR)"

clean:
	swift package clean
	rm -rf .build

test: release
	@echo "Testing $(BINARY_NAME)..."
	.build/release/$(BINARY_NAME) --help
	@echo "Basic test passed"
