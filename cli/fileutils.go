package main

import (
	"archive/zip"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
)

func copyDirectory(scrDir, dest string) {
	entries, err := os.ReadDir(scrDir)
	checkErr(err)
	for _, entry := range entries {
		sourcePath := filepath.Join(scrDir, entry.Name())
		destPath := filepath.Join(dest, entry.Name())
		fileInfo, err := os.Stat(sourcePath)
		checkErr(err)
		switch fileInfo.Mode() & os.ModeType {
		case os.ModeDir:
			createIfNotExists(destPath, 0755)
			copyDirectory(sourcePath, destPath)
		case os.ModeSymlink:
			copySymlink(sourcePath, destPath)
		default:
			copyFile(sourcePath, destPath)
		}
		fInfo, err := entry.Info()
		checkErr(err)
		isSymlink := fInfo.Mode()&os.ModeSymlink != 0
		if !isSymlink {
			checkErr(os.Chmod(destPath, fInfo.Mode()))
		}
	}
}

func copyFile(src, dest string) {
	data, err := ioutil.ReadFile(src)
	checkErr(err)
	copyData(data, dest)
}

func copyData(src []byte, dst string) {
	checkErr(os.WriteFile(dst, src, os.ModePerm))
}

func exists(filePath string) bool {
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return false
	}
	return true
}

func createIfNotExists(dir string, perm os.FileMode) {
	if !exists(dir) {
		checkErr(os.MkdirAll(dir, perm))
	}
}

func copySymlink(source, dest string) {
	link, err := os.Readlink(source)
	checkErr(err)
	checkErr(os.Symlink(link, dest))
}

func safeSymlink(src, dst string) {
	createIfNotExists(filepath.Dir(dst), os.ModePerm)
	checkErr(os.RemoveAll(dst))
	checkErr(os.Symlink(src, dst))
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
