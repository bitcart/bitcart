import json
import os
import shutil

from jsonschema import validate
from packaging.requirements import Requirement

from api import settings, utils
from api.constants import VERSION


def get_plugins():
    plugins = []
    for author in os.listdir(settings.settings.plugins_dir):
        for plugin in os.listdir(os.path.join(settings.settings.plugins_dir, author)):
            manifest_path = os.path.join(settings.settings.plugins_dir, author, plugin, "manifest.json")
            if not os.path.exists(manifest_path):
                continue
            with open(manifest_path) as f:
                manifest = f.read()
            try:
                plugins.append(parse_manifest(manifest))
            except ValueError:
                continue
    return plugins


def parse_manifest(manifest):
    try:
        manifest = json.loads(manifest)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid manifest.json: invalid JSON") from e
    try:
        validate(manifest, schema=settings.settings.plugins_schema)
    except Exception as e:
        raise ValueError(f"Invalid manifest.json: {e}") from e
    # validate version constraints
    version_constraint = manifest["constraints"]["bitcart"]
    req = Requirement(f"bitcart{version_constraint}")
    if VERSION not in req.specifier:
        raise ValueError(
            f"Invalid manifest.json: plugin requires Bitcart version{version_constraint}, but current version is {VERSION}"
        )
    return manifest


def get_moved_name(manifest, install):
    variants = {
        "backend": settings.settings.backend_plugins_dir,
        "admin": settings.settings.admin_plugins_dir,
        "store": settings.settings.store_plugins_dir,
        "daemon": settings.settings.daemon_plugins_dir,
        "docker": settings.settings.docker_plugins_dir,
    }
    org_name = manifest["author"].lower()
    if install["type"] in ("admin", "store"):
        org_name = "@" + org_name
    if install["type"] == "docker":
        return os.path.join(variants[install["type"]], org_name + "_" + os.path.basename(install["path"]))
    return os.path.join(variants[install["type"]], org_name, os.path.basename(install["path"]))


def process_installation_hooks(path, manifest):
    for install in manifest["installs"]:
        moved_name = get_moved_name(manifest, install)
        if os.path.exists(moved_name):
            utils.files.remove_tree(moved_name)
        shutil.move(os.path.join(path, install["path"]), moved_name)


def uninstall_plugin(author, name):
    plugin_path = os.path.join(settings.settings.plugins_dir, author.lower(), name.lower())
    manifest_path = os.path.join(plugin_path, "manifest.json")
    if not os.path.exists(manifest_path):
        return
    with open(manifest_path) as f:
        manifest = f.read()
    manifest = parse_manifest(manifest)
    for install in manifest["installs"]:
        path = get_moved_name(manifest, install)
        if os.path.exists(path):
            utils.files.remove_tree(path)
    utils.files.remove_tree(plugin_path)
