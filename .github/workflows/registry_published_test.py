#!/usr/bin/env python3
"""Tests for registry_published.py."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import registry_published


class RegistryPublishedTest(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = pathlib.Path(self._tmpdir.name)
        self.modules_root = self.repo / "modules"
        self._cwd = os.getcwd()
        self.addCleanup(os.chdir, self._cwd)
        os.chdir(self.repo)
        self.git("init")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "test@example.com")

    def git(self, *args):
        subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True)

    def write_module(self, name, versions, *, dirs=None, yanked_versions=None):
        module_dir = self.modules_root / name
        module_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "versions": versions,
            "yanked_versions": yanked_versions or {},
        }
        (module_dir / "metadata.json").write_text(
            json.dumps(data, indent=4) + "\n")
        for version in (versions if dirs is None else dirs):
            version_dir = module_dir / version
            version_dir.mkdir(parents=True, exist_ok=True)
            (version_dir / "MODULE.bazel").write_text(f"# {name} {version}\n")

    def remove_module(self, name):
        module_dir = self.modules_root / name
        if not module_dir.exists():
            return
        for path in sorted(module_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        module_dir.rmdir()

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)

    def test_no_published_ref_means_everything_is_unpublished(self):
        self.write_module("alpha", ["1.0.envoy", "2.0.envoy"])
        self.write_module("beta", ["3.0.envoy"])
        self.commit("initial")

        published = registry_published.published_pairs("", self.modules_root)

        self.assertEqual(published, set())
        self.assertEqual(
            registry_published.unpublished_versions(self.modules_root, published),
            {
                "alpha": ["1.0.envoy", "2.0.envoy"],
                "beta": ["3.0.envoy"],
            })
        self.assertEqual(
            registry_published.prune_plan(self.modules_root, published),
            [{"module": "alpha", "version": "1.0.envoy"}])

    def test_published_ref_tracks_unpublished_versions_in_metadata_order(self):
        self.write_module("stable", ["1.0.envoy"])
        self.write_module("one", ["1.0.envoy"])
        self.write_module("many", ["1.0.envoy"])
        self.write_module("oldgone", ["1.0.envoy"])
        self.write_module("dirsync", ["1.0.envoy"], dirs=["1.0.envoy", "2.0.envoy"])
        self.commit("published")
        self.git("tag", "v1")

        self.write_module("stable", ["1.0.envoy"])
        self.write_module("one", ["1.0.envoy", "2.0.envoy"])
        self.write_module("many", ["1.0.envoy", "2.0.envoy", "3.0.envoy"])
        self.remove_module("oldgone")
        self.write_module("dirsync", ["1.0.envoy", "2.0.envoy", "3.0.envoy"])
        self.commit("current")

        published = registry_published.published_pairs("v1", self.modules_root)

        self.assertIn(("dirsync", "2.0.envoy"), published)
        self.assertEqual(
            registry_published.unpublished_versions(self.modules_root, published),
            {
                "one": ["2.0.envoy"],
                "many": ["2.0.envoy", "3.0.envoy"],
                "dirsync": ["3.0.envoy"],
            })
        self.assertEqual(
            registry_published.prune_plan(self.modules_root, published),
            [{"module": "many", "version": "2.0.envoy"}])

    def test_new_module_since_publish_prunes_all_but_last(self):
        self.write_module("published", ["1.0.envoy"])
        self.commit("published")
        self.git("tag", "v1")

        self.write_module("published", ["1.0.envoy"])
        self.write_module("fresh", ["0.1.envoy", "0.2.envoy", "0.3.envoy"])
        self.commit("current")

        published = registry_published.published_pairs("v1", self.modules_root)

        self.assertEqual(
            registry_published.unpublished_versions(self.modules_root, published),
            {"fresh": ["0.1.envoy", "0.2.envoy", "0.3.envoy"]})
        self.assertEqual(
            registry_published.prune_plan(self.modules_root, published),
            [
                {"module": "fresh", "version": "0.1.envoy"},
                {"module": "fresh", "version": "0.2.envoy"},
            ])


if __name__ == "__main__":
    unittest.main()
