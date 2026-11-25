.PHONY: help test test-backend test-frontend build lint clean

help:
	@echo "NEXTRON Management Commands"
	@echo "  make test           - Run full test suite"
	@echo "  make test-backend   - Run backend tests"
	@echo "  make test-frontend  - Run frontend web tests"
	@echo "  make build          - Build production images and assets"

test-backend:
	cd Backend && pytest

test-frontend:
	cd Frontend/Web && npm run typecheck && npm run build

test: test-frontend

build:
	cd Frontend/Web && npm run build
