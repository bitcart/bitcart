package main

import (
	"bytes"
	"embed"
	"path/filepath"
	"text/template"

	"github.com/AlecAivazis/survey/v2"
)

//go:embed plugin/*
var pluginsData embed.FS

var Version = "dev"
var envFile = "../conf/.env"
var schemaURL = "https://bitcartcc.com/schemas/plugin/1.1.0/plugin.schema.json"

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

var componentData = map[string]interface{}{
	"backend": map[string]interface{}{
		"name":      "bitcart",
		"validator": survey.WithValidator(backendDirectoryValidator),
	},
	"admin": map[string]interface{}{
		"name":      "bitcart-admin",
		"validator": survey.WithValidator(frontendDirectoryValidator),
	},
	"store": map[string]interface{}{
		"name":      "bitcart-store",
		"validator": survey.WithValidator(frontendDirectoryValidator),
	},
	"docker": map[string]interface{}{
		"name":      "bitcart-docker",
		"validator": survey.WithValidator(dockerDirectoryValidator),
	},
}

var basicPluginCreate = []*survey.Question{
	{
		Name:     "name",
		Prompt:   &survey.Input{Message: "Enter the name for your plugin"},
		Validate: survey.Required,
	},
	{
		Name:     "author",
		Prompt:   &survey.Input{Message: "Enter the author name for your plugin"},
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

func copyFileContents(src, dst string) {
	fileContent, err := pluginsData.ReadFile(src)
	checkErr(err)
	copyData(fileContent, dst)
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
