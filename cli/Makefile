all: get-deps build

get-deps:
	go get github.com/MrNaif2018/jsonrpc
	go get github.com/urfave/cli

build:
	go build bitcart-cli.go

dist:
	go get github.com/mitchellh/gox
	gox --output "bitcart-cli-{{.OS}}-{{.Arch}}"

release: clean dist

clean:
	rm -f bitcart-cli bitcart-cli-*