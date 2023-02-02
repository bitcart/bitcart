package main

import (
	"context"
	"encoding/base64"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"strings"

	"github.com/joho/godotenv"
	"github.com/urfave/cli/v2"
	"github.com/ybbus/jsonrpc/v3"
)

func getSpec(
	client *http.Client,
	endpoint string,
	user string,
	password string,
) map[string]interface{} {
	req, err := http.NewRequest("GET", endpoint+"/spec", nil)
	checkErr(err)
	req.SetBasicAuth(user, password)
	resp, err := client.Do(req)
	checkErr(err)
	defer resp.Body.Close()
	bodyBytes, _ := ioutil.ReadAll(resp.Body)
	return jsonDecodeBytes(bodyBytes)
}

func getDefaultURL(coin string) string {
	symbol := strings.ToUpper(coin)
	envHost := os.Getenv(symbol + "_HOST")
	envPort := os.Getenv(symbol + "_PORT")
	host := "localhost"
	if envHost != "" {
		host = envHost
	}
	var port = COINS[coin]
	if envPort != "" {
		port = envPort
	}
	return "http://" + host + ":" + port
}

func runCommand(c *cli.Context) (*jsonrpc.RPCResponse, map[string]interface{}, error) {
	args := c.Args()
	wallet := c.String("wallet")
	contract := c.String("contract")
	address := c.String("address")
	diskless := c.Bool("diskless")
	user := c.String("user")
	password := c.String("password")
	coin := c.String("coin")
	url := c.String("url")
	noSpec := c.Bool("no-spec")
	if url == "" {
		url = getDefaultURL(coin)
	}
	httpClient := &http.Client{}
	// initialize rpc client
	rpcClient := jsonrpc.NewClientWithOpts(url, &jsonrpc.RPCClientOpts{
		HTTPClient: httpClient,
		CustomHeaders: map[string]string{
			"Authorization": "Basic " + base64.StdEncoding.EncodeToString(
				[]byte(user+":"+password),
			),
		},
	})
	// some magic to make array with the last element being a dictionary with xpub in it
	sl := args.Slice()[1:]
	var params []interface{}
	keyParams := map[string]interface{}{
		"xpub": map[string]interface{}{
			"xpub":     wallet,
			"contract": contract,
			"address":  address,
			"diskless": diskless,
		},
	}
	acceptFlags := true
	i := 0
	for i < len(sl) {
		if sl[i] == "--" {
			acceptFlags = false
			i += 1
		}
		if strings.HasPrefix(sl[i], "--") && acceptFlags {
			if i+1 >= len(sl) {
				exitErr("Error: missing value for flag " + sl[i])
			}
			keyParams[sl[i][2:]] = sl[i+1]
			i += 1
		} else {
			params = append(params, sl[i])
		}
		i += 1
	}
	params = append(params, keyParams)
	// call RPC method
	result, err := rpcClient.Call(context.Background(), args.Get(0), params)
	if err != nil {
		return nil, nil, err
	}
	spec := map[string]interface{}{}
	if !noSpec {
		spec = getSpec(httpClient, url, user, password)
	}
	return result, spec, nil
}

func main() {
	app := cli.NewApp()
	app.Name = "bitcart-cli"
	app.Version = Version
	app.HideHelp = true
	app.Usage = "Call RPC methods from console"
	app.UsageText = "bitcart-cli method [args]"
	app.EnableBashCompletion = true
	app.Flags = []cli.Flag{
		&cli.BoolFlag{
			Name:    "help",
			Aliases: []string{"h"},
			Usage:   "show help",
		},
		&cli.StringFlag{
			Name:     "wallet",
			Aliases:  []string{"w"},
			Usage:    "specify wallet",
			Required: false,
			EnvVars:  []string{"BITCART_WALLET"},
		},
		&cli.StringFlag{
			Name:     "contract",
			Usage:    "specify contract",
			Required: false,
			EnvVars:  []string{"BITCART_CONTRACT"},
		},
		&cli.StringFlag{
			Name:     "address",
			Usage:    "specify address (XMR-only)",
			Required: false,
			EnvVars:  []string{"BITCART_ADDRESS"},
		},
		&cli.BoolFlag{
			Name:    "diskless",
			Aliases: []string{"d"},
			Usage:   "Load wallet in memory only",
			Value:   false,
			EnvVars: []string{"BITCART_DISKLESS"},
		},
		&cli.StringFlag{
			Name:    "coin",
			Aliases: []string{"c"},
			Usage:   "specify coin to use",
			Value:   "btc",
			EnvVars: []string{"BITCART_COIN"},
		},
		&cli.StringFlag{
			Name:    "user",
			Aliases: []string{"u"},
			Usage:   "specify daemon user",
			Value:   "electrum",
			EnvVars: []string{"BITCART_LOGIN"},
		},
		&cli.StringFlag{
			Name:    "password",
			Aliases: []string{"p"},
			Usage:   "specify daemon password",
			Value:   "electrumz",
			EnvVars: []string{"BITCART_PASSWORD"},
		},
		&cli.StringFlag{
			Name:     "url",
			Aliases:  []string{"U"},
			Usage:    "specify daemon URL (overrides defaults)",
			Required: false,
			EnvVars:  []string{"BITCART_DAEMON_URL"},
		},
		&cli.BoolFlag{
			Name:    "no-spec",
			Usage:   "Disables spec fetching for better exceptions display",
			Value:   false,
			EnvVars: []string{"BITCART_NO_SPEC"},
		},
	}
	app.BashComplete = func(c *cli.Context) {
		set := flag.NewFlagSet("app", 0)
		set.Parse([]string{"help"})
		output, _, err := runCommand(cli.NewContext(app, set, c))
		if err != nil || output.Error != nil {
			fmt.Println("plugin")
			return
		}
		output.Result = append(output.Result.([]interface{}), "plugin")
		for _, v := range output.Result.([]interface{}) {
			fmt.Println(v)
		}
	}
	app.Action = func(c *cli.Context) error {
		args := c.Args()
		if args.Len() >= 1 {
			result, spec, err := runCommand(c)
			checkErr(err)
			// Print either error if found or result
			if result.Error != nil {
				if len(spec) != 0 {
					if spec["error"] != nil {
						exitErr(jsonEncode(spec["error"]))
					}
					exceptions := spec["exceptions"].(map[string]interface{})
					errorCode := fmt.Sprint(result.Error.Code)
					if exception, ok := exceptions[errorCode]; ok {
						exception, _ := exception.(map[string]interface{})
						exitErr(
							exception["exc_name"].(string) + ": " + exception["docstring"].(string),
						)
					}
				}
				exitErr(jsonEncode(result.Error))
			} else {
				var v, ok = result.Result.(string)
				if ok {
					smartPrint(v)
				} else {
					smartPrint(jsonEncode(result.Result))
				}
				return nil
			}
		} else {
			cli.ShowAppHelp(c)
		}
		return nil
	}
	app.Commands = []*cli.Command{
		{
			Name:  "plugin",
			Usage: "Manage plugins",
			Subcommands: []*cli.Command{
				{
					Name:      "init",
					Action:    initPlugin,
					Usage:     "Create a new plugin",
					UsageText: "bitcart-cli plugin init <path>",
				},
				{
					Name:      "install",
					Action:    installPlugin,
					Usage:     "Install a plugin",
					UsageText: "bitcart-cli plugin install [command options] <path>",
					Flags: []cli.Flag{
						&cli.BoolFlag{
							Name:    "dev",
							Usage:   "Install in development mode (symlink instead of copying)",
							Value:   false,
							Aliases: []string{"D"},
						},
					},
				},
				{
					Name:      "uninstall",
					Action:    uninstallPlugin,
					Usage:     "Uninstall a plugin",
					UsageText: "bitcart-cli plugin uninstall <path>",
				},
				{
					Name:      "validate",
					Action:    validatePlugin,
					Usage:     "Validate plugin manifest and common checks",
					UsageText: "bitcart-cli plugin validate <path>",
					Flags: []cli.Flag{
						&cli.StringFlag{
							Name:  "schema",
							Usage: "Supply custom schema URL",
							Value: schemaURL,
						},
					},
				},
				{
					Name:      "package",
					Action:    packagePlugin,
					Usage:     "Package plugin from its directory",
					UsageText: "bitcart-cli plugin package [command options] <path>",
					Flags: []cli.Flag{
						&cli.BoolFlag{
							Name:  "no-strip",
							Usage: "Don't strip unneccesary files from the package (i.e. node_modules)",
							Value: false,
						},
					},
				},
			},
		},
	}
	godotenv.Load(envFile)
	err := app.Run(os.Args)
	checkErr(err)
}
