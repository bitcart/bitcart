package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"

	"github.com/AlecAivazis/survey/v2"
	"github.com/urfave/cli/v2"
	"golang.org/x/exp/slices"
)

type ComponentType struct {
	Type string
	Path string
}

type BasicCreatePluginAnswers struct {
	Name           string
	Author         string
	Description    string
	ComponentTypes []string
	FinalTypes     []ComponentType
}

func initPlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	path, err := filepath.Abs(path)
	createIfNotExists(path, os.ModePerm)
	checkErr(err)
	answers := BasicCreatePluginAnswers{}
	checkErr(survey.Ask(basicPluginCreate, &answers))
	if slices.Contains(answers.ComponentTypes, "backend") {
		var backendPath string
		var componentName string
		checkErr(
			survey.AskOne(
				&survey.Input{
					Message: "Enter name of your backend component (i.e. name of the subfolder)",
				},
				&componentName,
				survey.WithValidator(survey.Required),
			),
		)
		checkErr(
			survey.AskOne(
				&survey.Input{Message: "Enter the path to cloned bitcart repository"},
				&backendPath,
				survey.WithValidator(survey.Required),
				survey.WithValidator(directoryValidator),
				survey.WithValidator(backendDirectoryValidator),
			),
		)
		backendPath, err := filepath.Abs(backendPath)
		checkErr(err)
		internalPath := filepath.Join(path, "src/backend/"+componentName)
		answers.FinalTypes = append(
			answers.FinalTypes,
			ComponentType{Type: "backend", Path: "src/backend/" + componentName},
		)
		data := struct {
			Name string
		}{Name: componentName}
		createIfNotExists(internalPath, os.ModePerm)
		checkErr(
			ioutil.WriteFile(
				filepath.Join(internalPath, "plugin.py"),
				executeTemplate("plugin/src/backend/plugin.py.tmpl", data, false),
				os.ModePerm,
			),
		)
		safeSymlink(
			internalPath,
			filepath.Join(
				backendPath,
				getOutputDirectory("backend", answers.Author, componentName),
			),
		)
	}
	if slices.Contains(answers.ComponentTypes, "docker") {
		var dockerPath string
		var componentName string
		checkErr(
			survey.AskOne(
				&survey.Input{
					Message: "Enter name of your docker component (i.e. name of the subfolder)",
				},
				&componentName,
				survey.WithValidator(survey.Required),
			),
		)
		checkErr(
			survey.AskOne(
				&survey.Input{Message: "Enter the path to cloned bitcart-docker repository"},
				&dockerPath,
				survey.WithValidator(survey.Required),
				survey.WithValidator(directoryValidator),
				survey.WithValidator(dockerDirectoryValidator),
			),
		)
		dockerPath, err := filepath.Abs(dockerPath)
		checkErr(err)
		internalPath := filepath.Join(path, "src/docker/"+componentName)
		answers.FinalTypes = append(
			answers.FinalTypes,
			ComponentType{Type: "docker", Path: "src/docker/" + componentName},
		)
		createIfNotExists(internalPath, os.ModePerm)
		safeSymlink(
			internalPath,
			filepath.Join(
				dockerPath,
				getOutputDirectory("docker", answers.Author, componentName),
			),
		)
	}
	for _, componentType := range []string{"admin", "store"} {
		if slices.Contains(answers.ComponentTypes, componentType) {
			var frontendPath string
			var componentName string
			checkErr(
				survey.AskOne(
					&survey.Input{
						Message: fmt.Sprintf(
							"Enter name of your %s component (i.e. name of the subfolder)",
							componentType,
						),
					},
					&componentName,
					survey.WithValidator(survey.Required),
				),
			)
			checkErr(
				survey.AskOne(
					&survey.Input{
						Message: fmt.Sprintf(
							"Enter the path to cloned %s frontend repository",
							componentType,
						),
					},
					&frontendPath,
					survey.WithValidator(survey.Required),
					survey.WithValidator(directoryValidator),
					survey.WithValidator(frontendDirectoryValidator),
				),
			)
			frontendPath, err := filepath.Abs(frontendPath)
			checkErr(err)
			answers.FinalTypes = append(
				answers.FinalTypes,
				ComponentType{
					Type: componentType,
					Path: "src/" + componentType + "/" + componentName,
				},
			)
			internalPath := filepath.Join(path, "src/"+componentType+"/"+componentName)
			createIfNotExists(internalPath, os.ModePerm)
			createIfNotExists(filepath.Join(internalPath, "config"), os.ModePerm)
			for _, file := range []string{"index.js", "config/extends.js", "config/routes.js"} {
				copyFileContents(
					filepath.Join("plugin/src/frontend", file),
					filepath.Join(internalPath, file),
				)
			}
			data := struct {
				Author string
				Name   string
			}{Author: answers.Author, Name: componentName}
			checkErr(
				ioutil.WriteFile(
					filepath.Join(internalPath, "package.json"),
					executeTemplate("plugin/src/frontend/package.json.tmpl", data, false),
					os.ModePerm,
				),
			)
			checkErr(
				ioutil.WriteFile(
					filepath.Join(internalPath, "config/index.js"),
					executeTemplate("plugin/src/frontend/config/index.js.tmpl", data, false),
					os.ModePerm,
				),
			)
			safeSymlink(
				internalPath,
				filepath.Join(
					frontendPath,
					getOutputDirectory(componentType, answers.Author, componentName),
				),
			)
		}
	}
	checkErr(
		ioutil.WriteFile(
			filepath.Join(path, "manifest.json"),
			executeTemplate("plugin/manifest.json.tmpl", answers, true),
			os.ModePerm,
		),
	)
	checkErr(
		ioutil.WriteFile(
			filepath.Join(path, ".gitignore"),
			executeTemplate("plugin/.gitignore.tmpl", answers, true),
			os.ModePerm,
		),
	)
	copyFileContents("plugin/.editorconfig", filepath.Join(path, ".editorconfig"))
	fmt.Println("Plugin created successfully")
	return nil
}

type pluginMoveAction func(string, string)

func pluginActionBase(path string, fn pluginMoveAction) {
	path, err := filepath.Abs(path)
	checkErr(err)
	manifest := readManifest(path).(map[string]interface{})
	paths := make(map[string]interface{})
	iterateInstallations(path, manifest, func(componentPath, componentName, installType string) {
		if _, ok := paths[installType]; !ok {
			checkErr(survey.Ask([]*survey.Question{
				{
					Name: installType,
					Prompt: &survey.Input{
						Message: fmt.Sprintf(
							"Enter the path to cloned %s repository",
							componentData[installType].(map[string]interface{})["name"].(string),
						),
					},
				},
			}, &paths, survey.WithValidator(survey.Required), survey.WithValidator(directoryValidator), componentData[installType].(map[string]interface{})["validator"].(survey.AskOpt)))
		}
		finalPath := filepath.Join(
			paths[installType].(string),
			getOutputDirectory(installType, manifest["author"].(string), componentName),
		)
		fn(componentPath, finalPath)
	})
}

func installPlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	isDev := c.Bool("dev") || args.Get(1) == "--dev" || args.Get(1) == "-D"
	pluginActionBase(path, func(componentPath, finalPath string) {
		checkErr(os.RemoveAll(finalPath))
		if !isDev {
			copyDirectory(componentPath, finalPath)
		} else {
			safeSymlink(componentPath, finalPath)
		}
	})
	return nil
}

func uninstallPlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	pluginActionBase(path, func(componentPath, finalPath string) {
		checkErr(os.RemoveAll(finalPath))
	})
	return nil
}

func validatePlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	url := args.Get(2) // after --schema part
	if url == "" {
		url = c.String("schema")
	}
	sch := prepareSchema(url)
	manifest := readManifest(path)
	if err := sch.Validate(manifest); err != nil {
		log.Fatalf("%#v", err)
	}
	iterateInstallations(
		path,
		manifest.(map[string]interface{}),
		func(componentPath, componentName, installType string) {
			switch installType {
			case "backend":
				pluginBase := filepath.Join(componentPath, "plugin.py")
				if !validateFileExists(pluginBase) {
					log.Fatalf(
						"Plugin's backend component %s does not include plugin.py",
						componentPath,
					)
				}
			case "admin":
				validateFrontend("admin", componentPath)
			case "store":
				validateFrontend("store", componentPath)
			}
		},
	)
	fmt.Println("Plugin is valid!")
	return nil
}

func packagePlugin(c *cli.Context) error {
	args := c.Args()
	if args.Len() < 1 {
		return cli.ShowSubcommandHelp(c)
	}
	path := args.Get(0)
	manifest := readManifest(path).(map[string]interface{})
	noStrip := c.Bool("no-strip") || args.Get(1) == "--no-strip"
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
