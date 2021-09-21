package main

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"strings"

	"github.com/joho/godotenv"
	"github.com/urfave/cli/v2"
	"github.com/ybbus/jsonrpc/v2"
)

var Version = "dev"
var envFile = "../conf/.env"
var COINS = map[string]string{
	"btc": "5000",
	"ltc": "5001",
	// 5002 reserved for new coins
	"bsty": "5003",
	"bch":  "5004",
	"xrg":  "5005",
}

func getSpec(client *http.Client, endpoint string, user string, password string) map[string]interface{} {
	req, err := http.NewRequest("GET", endpoint+"/spec", nil)
	checkErr(err)
	req.SetBasicAuth(user, password)
	resp, err := client.Do(req)
	checkErr(err)
	defer resp.Body.Close()
	bodyBytes, _ := ioutil.ReadAll(resp.Body)
	return jsonDecodeBytes(bodyBytes)
}

func smartPrint(text string) {
	text = strings.TrimRight(text, "\r\n")
	fmt.Println(text)
}

func exitErr(err string) {
	smartPrint(err)
	os.Exit(1)
}

func checkErr(err error) {
	if err != nil {
		exitErr("Error: " + err.Error())
	}
}

func jsonEncode(data interface{}) string {
	buf := new(bytes.Buffer)
	encoder := json.NewEncoder(buf)
	encoder.SetIndent("", "  ")
	encoder.SetEscapeHTML(false)
	err := encoder.Encode(data)
	checkErr(err)
	return string(buf.String())
}

func jsonDecodeBytes(data []byte) map[string]interface{} {
	var result map[string]interface{}
	err := json.Unmarshal(data, &result)
	checkErr(err)
	return result
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

func main() {

	app := cli.NewApp()
	app.Name = "Bitcart CLI"
	app.Version = Version
	app.HideHelp = true
	app.Usage = "Call RPC methods from console"
	app.UsageText = "bitcart-cli method [args]"
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
	app.Action = func(c *cli.Context) error {
		args := c.Args()
		if args.Len() >= 1 {
			// load flags
			wallet := c.String("wallet")
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
					"Authorization": "Basic " + base64.StdEncoding.EncodeToString([]byte(user+":"+password)),
				},
			})
			// some magic to make array with the last element being a dictionary with xpub in it
			sl := args.Slice()[1:]
			params := make([]interface{}, len(sl))
			for i := range sl {
				params[i] = sl[i]
			}
			params = append(params, map[string]interface{}{"xpub": wallet})
			// call RPC method
			result, err := rpcClient.Call(args.Get(0), params)
			checkErr(err)
			// Print either error if found or result
			if result.Error != nil {
				if !noSpec {
					spec := getSpec(httpClient, url, user, password)
					if spec["error"] != nil {
						exitErr(jsonEncode(spec["error"]))
					}
					exceptions := spec["exceptions"].(map[string]interface{})
					errorCode := fmt.Sprint(result.Error.Code)
					if exception, ok := exceptions[errorCode]; ok {
						exception, _ := exception.(map[string]interface{})
						exitErr(exception["exc_name"].(string) + ": " + exception["docstring"].(string))
					}
				}
				exitErr(jsonEncode(result.Error))
			} else {
				smartPrint(jsonEncode(result.Result))
				return nil
			}
		} else {
			cli.ShowAppHelp(c)
		}
		return nil
	}
	err := godotenv.Load(envFile)
	checkErr(err)
	err = app.Run(os.Args)
	checkErr(err)
}
