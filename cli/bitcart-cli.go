package main

import (
	"archive/zip"
	"bufio"
	"bytes"
	"context"
	"embed"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"text/template"
	"time"
	"unicode"

	"github.com/AlecAivazis/survey/v2"
	"github.com/joho/godotenv"
	"github.com/santhosh-tekuri/jsonschema/v5"
	_ "github.com/santhosh-tekuri/jsonschema/v5/httploader"
	"github.com/urfave/cli/v2"
	"github.com/ybbus/jsonrpc/v3"
	"golang.org/x/exp/slices"
)

//go:embed plugin/*
var pluginsData embed.FS

var Version = "dev"
var envFile = "../conf/.env"
var schemaURL = "https://bitcartcc.com/schemas/plugin/1.0.0/plugin.schema.json"

var COINS = map[string]string{
	"btc":   "5000",
	"ltc":   "5001",
	"eth":   "5002",
	"bsty":  "5003",
	"bch":   "5004",
	"xrg":   "5005",
	"bnb":   "5006",
	"sbch":  "5007",
	"matic": "5008",
	"trx":   "5009",
	"grs":   "5010",
	"xmr":   "5011",
}

var basicPluginCreate = []*survey.Question{
	{
		Name:     "name",
		Prompt:   &survey.Input{Message: "Enter the name for your plugin"},
		Validate: survey.Required,
	},
	{
		Name:     "organization",
		Prompt:   &survey.Input{Message: "Enter the organization name for your plugin"},
		Validate: survey.Required,
	},
	{
		Name:   "description",
		Prompt: &survey.Input{Message: "Enter plugin description (optional)"},
	},
	{
		Name: "ComponentTypes",
		Prompt: &survey.MultiSelect{
			Message: "Select which components will your plugin update",
			Options: []string{"backend", "admin", "store", "docker"},
		},
	},
}

type ComponentType struct {
	Type string
	Path string
}

type BasicCreatePluginAnswers struct {
	Name           string
	Organization   string
	Description    string
	ComponentTypes []string
	FinalTypes     []ComponentType
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
			"Authorization": "Basic " + base64.StdEncoding.EncodeToString([]byte(user+":"+password)),
		},
	})
	// some magic to make array with the last element being a dictionary with xpub in it
	sl := args.Slice()[1:]
	var params []interface{}
	keyParams := map[string]interface{}{"xpub": map[string]interface{}{"xpub": wallet, "contract": contract, "address": address, "diskless": diskless}}
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

func getCacheDir() string {
	baseDir, _ := os.UserCacheDir()
	cacheDir := filepath.Join(baseDir, "bitcart-cli")
	if _, err := os.Stat(cacheDir); os.IsNotExist(err) {
		os.MkdirAll(cacheDir, os.ModePerm)
	}
	return cacheDir
}

func prepareSchema() *jsonschema.Schema {
	cacheDir := getCacheDir()
	schemaPath := filepath.Join(cacheDir, "plugin.schema.json")
	if statResult, err := os.Stat(schemaPath); os.IsNotExist(err) || time.Since(statResult.ModTime().AddDate(0, 0, 7)) > time.Since(time.Now()) {
		resp, err := http.Get(schemaURL)
		checkErr(err)
		defer resp.Body.Close()
		data, err := ioutil.ReadAll(resp.Body)
		checkErr(err)
		checkErr(ioutil.WriteFile(schemaPath, data, os.ModePerm))
	}
	sch, err := jsonschema.Compile(schemaPath)
	checkErr(err)
	return sch
}

func validateFileExists(path string) bool {
	if _, err := os.Stat(path); os.IsNotExist(err) {
		return false
	}
	return true
}

func directoryValidator(val interface{}) error {
	statResult, err := os.Stat(val.(string))
	if os.IsNotExist(err) {
		return errors.New("Directory does not exist")
	}
	if !statResult.IsDir() {
		return errors.New("Path is not a directory")
	}
	return nil
}

func backendDirectoryValidator(val interface{}) error {
	if !validateFileExists(filepath.Join(val.(string), "gunicorn.conf.py")) {
		return errors.New("Directory does not look to be a cloned https://github.com/bitcartcc/bitcart repository")
	}
	return nil
}

func dockerDirectoryValidator(val interface{}) error {
	if !validateFileExists(filepath.Join(val.(string), "setup.sh")) {
		return errors.New("Directory does not look to be a cloned https://github.com/bitcartcc/bitcart-docker repository")
	}
	return nil
}

func frontendDirectoryValidator(val interface{}) error {
	if !validateFileExists(filepath.Join(val.(string), "nuxt.config.js")) {
		return errors.New("Directory does not look to be a frontend repository")
	}
	return nil
}

func validateFrontend(componentType string, path string) {
	for _, file := range []string{"index.js", "package.json", "config/index.js"} {
		if !validateFileExists(filepath.Join(path, file)) {
			log.Fatalf("Plugin's %s component %s does not include %s", componentType, path, file)
		}
	}
}

func readManifest(path string) interface{} {
	manifestPath := filepath.Join(path, "manifest.json")
	data, err := ioutil.ReadFile(manifestPath)
	checkErr(err)
	var manifest interface{}
	checkErr(json.Unmarshal(data, &manifest))
	return manifest
}

func validatePlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	sch := prepareSchema()
	manifest := readManifest(path)
	if err := sch.Validate(manifest); err != nil {
		log.Fatalf("%#v", err)
	}
	for _, installData := range manifest.(map[string]interface{})["installs"].([]interface{}) {
		installData := installData.(map[string]interface{})
		componentPath := filepath.Join(path, installData["path"].(string))
		switch installData["type"] {
		case "backend":
			pluginBase := filepath.Join(componentPath, "plugin.py")
			if !validateFileExists(pluginBase) {
				log.Fatalf("Plugin's backend component %s does not include plugin.py", componentPath)
			}
		case "admin":
			validateFrontend("admin", componentPath)
		case "store":
			validateFrontend("store", componentPath)
		}
	}
	fmt.Println("Plugin is valid!")
	return nil
}

func createZip(in string, out string) {
	file, err := os.Create(out)
	checkErr(err)
	defer file.Close()
	w := zip.NewWriter(file)
	defer w.Close()
	walker := func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		relPath, err := filepath.Rel(in, path)
		checkErr(err)
		if relPath == filepath.Base(out) {
			return nil
		}
		if relPath == ".git" {
			return filepath.SkipDir
		}
		fmt.Printf("Crawling: %#v\n", relPath)
		if info.IsDir() {
			return nil
		}
		file, err := os.Open(path)
		checkErr(err)
		defer file.Close()
		checkErr(err)
		f, err := w.Create(relPath)
		checkErr(err)
		_, err = io.Copy(f, file)
		checkErr(err)
		return nil
	}
	checkErr(filepath.Walk(in, walker))
}

func packagePlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	manifest := readManifest(path).(map[string]interface{})
	noStrip := c.Bool("no-strip")
	if !noStrip {
		walker := func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return nil
			}
			if info.IsDir() {
				if info.Name() == "node_modules" || info.Name() == "__pycache__" {
					return os.RemoveAll(path)
				}
				return nil
			}
			if info.Name() == "yarn.lock" || info.Name() == "package-lock.json" {
				return os.RemoveAll(path)
			}
			return nil
		}
		checkErr(filepath.Walk(path, walker))
	}
	outPath := filepath.Join(path, manifest["name"].(string)+".bitcartcc")
	createZip(path, outPath)
	fmt.Println("Plugin packaged to", outPath)
	return nil
}

func isBlank(str string) bool {
	for _, r := range str {
		if !unicode.IsSpace(r) {
			return false
		}
	}
	return true
}

func removeBlankLines(reader io.Reader, writer io.Writer) {
	breader := bufio.NewReader(reader)
	bwriter := bufio.NewWriter(writer)
	for {
		line, err := breader.ReadString('\n')
		if !isBlank(line) {
			bwriter.WriteString(line)
		}
		if err != nil {
			break
		}
	}
	bwriter.Flush()
}

func executeTemplate(templatePath string, data interface{}, stripSpaces bool) []byte {
	tmpl, err := template.New(filepath.Base(templatePath)).Funcs(template.FuncMap{
		"IsLast": func(i, size int) bool { return i == size-1 },
	}).ParseFS(pluginsData, templatePath)
	checkErr(err)
	buf := new(bytes.Buffer)
	checkErr(tmpl.ExecuteTemplate(buf, filepath.Base(templatePath), &data))
	if !stripSpaces {
		return buf.Bytes()
	}
	newBuf := new(bytes.Buffer)
	removeBlankLines(bytes.NewReader(buf.Bytes()), newBuf)
	return newBuf.Bytes()
}

func safeSymlink(src, dst string) {
	os.MkdirAll(filepath.Dir(dst), os.ModePerm)
	os.Remove(dst)
	checkErr(os.Symlink(src, dst))
}

func copyFileContents(src, dst string) {
	fileContent, err := pluginsData.ReadFile(src)
	checkErr(err)
	checkErr(os.WriteFile(dst, fileContent, os.ModePerm))
}

func initPlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	path, err := filepath.Abs(path)
	os.MkdirAll(path, os.ModePerm)
	checkErr(err)
	answers := BasicCreatePluginAnswers{}
	checkErr(survey.Ask(basicPluginCreate, &answers))
	if slices.Contains(answers.ComponentTypes, "backend") {
		var backendPath string
		var componentName string
		checkErr(survey.AskOne(&survey.Input{Message: "Enter name of your backend component (i.e. name of the subfolder)"}, &componentName, survey.WithValidator(survey.Required)))
		checkErr(survey.AskOne(&survey.Input{Message: "Enter the path to cloned bitcart repository"}, &backendPath, survey.WithValidator(survey.Required), survey.WithValidator(directoryValidator), survey.WithValidator(backendDirectoryValidator)))
		backendPath, err := filepath.Abs(backendPath)
		checkErr(err)
		internalPath := filepath.Join(path, "src/backend/"+componentName)
		answers.FinalTypes = append(answers.FinalTypes, ComponentType{Type: "backend", Path: "src/backend/" + componentName})
		data := struct {
			Name string
		}{Name: componentName}
		os.MkdirAll(internalPath, os.ModePerm)
		checkErr(ioutil.WriteFile(filepath.Join(internalPath, "plugin.py"), executeTemplate("plugin/src/backend/plugin.py.tmpl", data, false), os.ModePerm))
		safeSymlink(internalPath, filepath.Join(backendPath, "modules", answers.Organization, componentName))
	}
	if slices.Contains(answers.ComponentTypes, "docker") {
		var dockerPath string
		var componentName string
		checkErr(survey.AskOne(&survey.Input{Message: "Enter name of your docker component (i.e. name of the subfolder)"}, &componentName, survey.WithValidator(survey.Required)))
		checkErr(survey.AskOne(&survey.Input{Message: "Enter the path to cloned bitcart-docker repository"}, &dockerPath, survey.WithValidator(survey.Required), survey.WithValidator(directoryValidator), survey.WithValidator(dockerDirectoryValidator)))
		dockerPath, err := filepath.Abs(dockerPath)
		checkErr(err)
		internalPath := filepath.Join(path, "src/docker/"+componentName)
		answers.FinalTypes = append(answers.FinalTypes, ComponentType{Type: "docker", Path: "src/docker/" + componentName})
		os.MkdirAll(internalPath, os.ModePerm)
		safeSymlink(internalPath, filepath.Join(dockerPath, "compose/plugins/docker", answers.Organization+"_"+componentName))
	}
	for _, componentType := range []string{"admin", "store"} {
		if slices.Contains(answers.ComponentTypes, componentType) {
			var frontendPath string
			var componentName string
			checkErr(survey.AskOne(&survey.Input{Message: fmt.Sprintf("Enter name of your %s component (i.e. name of the subfolder)", componentType)}, &componentName, survey.WithValidator(survey.Required)))
			checkErr(survey.AskOne(&survey.Input{Message: fmt.Sprintf("Enter the path to cloned %s frontend repository", componentType)}, &frontendPath, survey.WithValidator(survey.Required), survey.WithValidator(directoryValidator), survey.WithValidator(frontendDirectoryValidator)))
			frontendPath, err := filepath.Abs(frontendPath)
			checkErr(err)
			answers.FinalTypes = append(answers.FinalTypes, ComponentType{Type: componentType, Path: "src/" + componentType + "/" + componentName})
			internalPath := filepath.Join(path, "src/"+componentType+"/"+componentName)
			os.MkdirAll(internalPath, os.ModePerm)
			os.MkdirAll(filepath.Join(internalPath, "config"), os.ModePerm)
			for _, file := range []string{"index.js", "config/extends.js", "config/routes.js"} {
				copyFileContents(filepath.Join("plugin/src/frontend", file), filepath.Join(internalPath, file))
			}
			data := struct {
				Organization string
				Name         string
			}{Organization: answers.Organization, Name: componentName}
			checkErr(ioutil.WriteFile(filepath.Join(internalPath, "package.json"), executeTemplate("plugin/src/frontend/package.json.tmpl", data, false), os.ModePerm))
			checkErr(ioutil.WriteFile(filepath.Join(internalPath, "config/index.js"), executeTemplate("plugin/src/frontend/config/index.js.tmpl", data, false), os.ModePerm))
			safeSymlink(internalPath, filepath.Join(frontendPath, "modules", "@"+answers.Organization, componentName))
		}
	}
	checkErr(ioutil.WriteFile(filepath.Join(path, "manifest.json"), executeTemplate("plugin/manifest.json.tmpl", answers, true), os.ModePerm))
	checkErr(ioutil.WriteFile(filepath.Join(path, ".gitignore"), executeTemplate("plugin/.gitignore.tmpl", answers, true), os.ModePerm))
	copyFileContents("plugin/.editorconfig", filepath.Join(path, ".editorconfig"))
	fmt.Println("Plugin created successfully")
	return nil
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
						exitErr(exception["exc_name"].(string) + ": " + exception["docstring"].(string))
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
					Name:      "validate",
					Action:    validatePlugin,
					Usage:     "Validate plugin manifest and common checks",
					UsageText: "bitcart-cli plugin validate <path>",
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
