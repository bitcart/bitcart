all: get-deps build

get-deps:
	go get github.com/ybbus/jsonrpc
	go get github.com/urfave/cli

build:
	go build ${ARGS} bitcart-cli.go

dist:
	go get github.com/mitchellh/gox
	gox --output "dist/bitcart-cli-{{.OS}}-{{.Arch}}" ${ARGS}

release: clean dist

clean:
	rm -f bitcart-cli bitcart-cli-*
