import json
import os
import shutil

from jsonschema import validate
from packaging.requirements import Requirement

from api import settings
from api.constants import VERSION


def get_plugins():
    plugins = []
    for organization in os.listdir(settings.settings.plugins_dir):
        for plugin in os.listdir(os.path.join(settings.settings.plugins_dir, organization)):
            manifest_path = os.path.join(settings.settings.plugins_dir, organization, plugin, "manifest.json")
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
    except json.JSONDecodeError:
        raise ValueError("Invalid manifest.json: invalid JSON")
    try:
        validate(manifest, schema=settings.settings.plugins_schema)
    except Exception as e:
        raise ValueError(f"Invalid manifest.json: {e}")
    # validate version constraints
    version_constraint = manifest["constraints"]["bitcartcc"]
    req = Requirement(f"bitcartcc{version_constraint}")
    if VERSION not in req.specifier:
        raise ValueError(
            f"Invalid manifest.json: plugin requires BitcartCC version{version_constraint}, but current version is {VERSION}"
        )
    return manifest


def get_moved_name(manifest, install):
    variants = {
        "backend": "modules",
        "admin": settings.settings.admin_plugins_dir,
        "store": settings.settings.store_plugins_dir,
        "docker-compose": settings.settings.docker_plugins_dir,
    }
    org_name = manifest["organization"].lower()
    if install["type"] in ("admin", "store"):
        org_name = "@" + org_name
    return os.path.join(variants[install["type"]], org_name, os.path.basename(install["path"]))


def process_installation_hooks(path, manifest):
    for install in manifest["installs"]:
        moved_name = get_moved_name(manifest, install)
        if os.path.exists(moved_name):
            shutil.rmtree(moved_name)
        shutil.move(os.path.join(path, install["path"]), moved_name)


def uninstall_plugin(organization, name):
    plugin_path = os.path.join(settings.settings.plugins_dir, organization.lower(), name.lower())
    manifest_path = os.path.join(plugin_path, "manifest.json")
    if not os.path.exists(manifest_path):
        return
    with open(manifest_path) as f:
        manifest = f.read()
    manifest = parse_manifest(manifest)
    for install in manifest["installs"]:
        path = get_moved_name(manifest, install)
        if os.path.exists(path):
            shutil.rmtree(path)
    shutil.rmtree(plugin_path)
