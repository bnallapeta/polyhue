.PHONY: all components compose run server audience clean help

# Build targets per component
COLOR_RS    := components/color-rs/target/wasm32-wasip2/release/color_rs.wasm
COLOR_PY    := components/color-py/color-py.wasm
COLOR_TS    := components/color-ts/dist/color-ts.wasm
POLICY_GATE := components/policy-gate/target/wasm32-wasip2/release/policy_gate.wasm

COMPOSED    := dist/polyhue.wasm

all: $(COMPOSED)

help:
	@echo "Targets:"
	@echo "  make            build all components and compose"
	@echo "  make components build the four tool components"
	@echo "  make compose    compose components into dist/polyhue.wasm"
	@echo "  make run        start the wasmcp server + audience proxy"
	@echo "  make server     start only the wasmcp server (port 3000)"
	@echo "  make audience   start only the audience proxy (port 8080)"
	@echo "  make clean      remove all build artifacts"

components: $(COLOR_RS) $(COLOR_PY) $(COLOR_TS) $(POLICY_GATE)

$(COLOR_RS):
	$(MAKE) -C components/color-rs

$(COLOR_PY):
	$(MAKE) -C components/color-py

$(COLOR_TS):
	$(MAKE) -C components/color-ts

$(POLICY_GATE):
	$(MAKE) -C components/policy-gate

compose: $(COMPOSED)

$(COMPOSED): $(COLOR_PY) $(COLOR_RS) $(COLOR_TS) $(POLICY_GATE)
	@mkdir -p dist
	wasmcp compose server \
		$(COLOR_PY) \
		$(COLOR_RS) \
		$(COLOR_TS) \
		$(POLICY_GATE) \
		-o $(COMPOSED) --force
	@ls -lh $(COMPOSED)

run: $(COMPOSED)
	@echo "wasmcp server → http://localhost:3000/mcp"
	@echo "audience page → http://localhost:8080/"
	@echo "Ctrl-C to stop both."
	@trap 'kill 0' INT TERM; \
		spin up -f $(COMPOSED) & \
		( sleep 3 && cd audience && python3 serve.py ) & \
		wait

server: $(COMPOSED)
	spin up -f $(COMPOSED)

audience:
	cd audience && python3 serve.py

clean:
	$(MAKE) -C components/color-rs clean
	$(MAKE) -C components/color-py clean
	$(MAKE) -C components/color-ts clean
	$(MAKE) -C components/policy-gate clean
	rm -rf dist
