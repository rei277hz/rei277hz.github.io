"""Check published bytes, redirect behavior, and replacement boundaries."""

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import build_site


NODE = os.environ.get("NODE_BINARY") or shutil.which("node")


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.scripts = []
        self.in_script = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "script":
            self.in_script = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, value):
        if self.in_script:
            self.scripts[-1] += value


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name) / "checkout"
        self.source.mkdir()
        self.payloads = {
            "color-picker/index.html": b'<script src="./assets/app.js"></script>',
            "color-picker/assets/app.js": b"console.log('picker');\n",
            "color-picker/assets/core.wasm": bytes(range(256)),
            "perceptual-grade/index.html": b'<a href="en/index.html">English</a>',
            "perceptual-grade/en/index.html": b"<h1>Handbook</h1>",
            "perceptual-grade/.nojekyll": b"",
        }
        for name, data in self.payloads.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.redirects = {
            "/modcam16-hk-palette/": "/color-picker/",
            "/modcam16-hk-palette/decompose.html": "/color-picker/",
            "/modcam16-hk-ucs/": "/color-picker/",
        }
        self.write_redirects()

    def write_redirects(self, value=None):
        (self.source / "redirects.json").write_text(json.dumps(
            self.redirects if value is None else value), encoding="utf-8")

    def snapshot(self):
        return {str(path.relative_to(self.source / "_site")): path.read_bytes()
                for path in (self.source / "_site").rglob("*") if path.is_file()}

    def assert_rejected_without_replacing_site(self):
        before = self.snapshot()
        with self.assertRaises((ValueError, OSError)):
            build_site.build_site(self.source)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(list(self.source.glob(".site-build-*")), [])

    def test_copies_only_current_sites_and_generates_redirect_artifacts(self):
        (self.source / ".git").mkdir()
        (self.source / ".git/config").write_bytes(b"private metadata")
        (self.source / "modcam16-hk-palette/assets").mkdir(parents=True)
        (self.source / "modcam16-hk-palette/assets/old.js").write_bytes(b"obsolete")
        (self.source / "README.md").write_text("maintainer documentation")
        output = build_site.build_site(self.source)
        self.assertEqual(output, self.source / "_site")
        for name, data in self.payloads.items():
            self.assertEqual((output / name).read_bytes(), data)
            self.assertEqual((self.source / name).read_bytes(), data)
        for absent in (".git", "README.md", "redirects.json", "modcam16-hk-palette/assets"):
            self.assertFalse((output / absent).exists(), absent)
        self.assertEqual((self.source / "modcam16-hk-palette/assets/old.js").read_bytes(), b"obsolete")
        self.assertTrue((output / ".nojekyll").is_file())
        self.assertIn('href="/color-picker/"', (output / "index.html").read_text())
        self.assertIn('href="/perceptual-grade/"', (output / "index.html").read_text())
        for name in ("modcam16-hk-palette/index.html", "modcam16-hk-palette/decompose.html",
                     "modcam16-hk-ucs/index.html"):
            page = Page((output / name).read_text())
            self.assertIn(("link", {"rel": "canonical", "href": "/color-picker/"}), page.tags)
            self.assertIn(("meta", {"http-equiv": "refresh", "content": "0; url=/color-picker/"}), page.tags)
            self.assertIn(("a", {"href": "/color-picker/"}), page.tags)

    def test_rebuild_removes_stale_output_and_uses_current_product_bytes(self):
        output = build_site.build_site(self.source)
        (output / ".stale").write_text("old output")
        (output / "stale-directory").mkdir()
        (output / "stale-directory/old.txt").write_text("old output")
        (self.source / "color-picker/assets/app.js").write_bytes(b"new app")
        del self.redirects["/modcam16-hk-ucs/"]
        self.write_redirects()
        build_site.build_site(self.source)
        self.assertEqual((output / "color-picker/assets/app.js").read_bytes(), b"new app")
        for old in (".stale", "stale-directory", "modcam16-hk-ucs"):
            self.assertFalse((output / old).exists())

    def test_invalid_manifest_leaves_previous_site_intact(self):
        build_site.build_site(self.source)
        for text in ('not JSON', '[]', '{"/old/": "/color-picker/", "/old/": "/perceptual-grade/"}'):
            with self.subTest(text=text):
                (self.source / "redirects.json").write_text(text)
                self.assert_rejected_without_replacing_site()

    def test_unsafe_or_noncanonical_urls_leave_previous_site_intact(self):
        build_site.build_site(self.source)
        for old in ("https://elsewhere.example/", "//elsewhere/", "/../escape/", "/a/../b/",
                    "/a//b/", "/a\\b/", "/%2e%2e/", "/old/?q=x", "/old/#fragment",
                    "/old\n/", "/.git/", "/", "/old", '/</script>/'):
            with self.subTest(old=old):
                self.write_redirects({old: "/color-picker/"})
                self.assert_rejected_without_replacing_site()
        for target in ("https://elsewhere.example/", "//elsewhere/", "/%2foutside/", None, []):
            with self.subTest(target=target):
                self.write_redirects({"/old/": target})
                self.assert_rejected_without_replacing_site()

    def test_missing_targets_and_redirect_cycles_are_rejected(self):
        build_site.build_site(self.source)
        for mapping in (
            {"/old/": "/missing/"},
            {"/old/": "/old/"},
            {"/old/": "/older/", "/older/": "/old/"},
            {"/color-picker/assets/": "/color-picker/assets/app.js"},
        ):
            with self.subTest(mapping=mapping):
                self.write_redirects(mapping)
                self.assert_rejected_without_replacing_site()

    def test_current_pages_and_duplicate_output_paths_cannot_be_overwritten(self):
        build_site.build_site(self.source)
        for mapping in (
            {"/color-picker/": "/perceptual-grade/"},
            {"/index.html": "/color-picker/"},
            {"/404.html": "/color-picker/"},
            {"/old/": "/color-picker/", "/old/index.html": "/color-picker/"},
            {"/old.html": "/color-picker/", "/old.html/nested.html": "/color-picker/"},
            {"/color-picker/index.html/child.html": "/color-picker/"},
        ):
            with self.subTest(mapping=mapping):
                self.write_redirects(mapping)
                self.assert_rejected_without_replacing_site()

    def test_missing_product_or_index_preserves_previous_output(self):
        build_site.build_site(self.source)
        (self.source / "color-picker/index.html").unlink()
        self.assert_rejected_without_replacing_site()
        shutil.rmtree(self.source / "color-picker")
        self.assert_rejected_without_replacing_site()

    def test_product_symlinks_and_git_metadata_are_rejected(self):
        build_site.build_site(self.source)
        outside = Path(self.temporary.name) / "private"
        outside.write_bytes(b"outside data")
        link = self.source / "color-picker/assets/link"
        link.symlink_to(outside)
        self.assert_rejected_without_replacing_site()
        link.unlink()
        metadata = self.source / "color-picker/.git"
        metadata.mkdir()
        (metadata / "config").write_text("private")
        self.assert_rejected_without_replacing_site()
        self.assertEqual(outside.read_bytes(), b"outside data")

    def test_unowned_output_and_symlinked_output_are_never_removed(self):
        output = self.source / "_site"
        output.mkdir()
        (output / "keep").write_bytes(b"unrelated data")
        with self.assertRaisesRegex(ValueError, "ownership marker"):
            build_site.build_site(self.source)
        self.assertEqual((output / "keep").read_bytes(), b"unrelated data")
        shutil.rmtree(output)
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (outside / "keep").write_bytes(b"outside data")
        output.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "ownership marker"):
            build_site.build_site(self.source)
        self.assertEqual((outside / "keep").read_bytes(), b"outside data")

    @unittest.skipUnless(NODE, "Set NODE_BINARY or install Node to execute redirect JavaScript")
    def test_generated_javascript_redirects_aliases_and_preserves_query_and_fragment(self):
        self.redirects.update({
            "/modcam16-hk-palette/archive/": "/perceptual-grade/",
            "/modcam16-hk-palette/archive/one.html": "/color-picker/",
        })
        self.write_redirects()
        output = build_site.build_site(self.source)
        runner = """
const fs = require('node:fs');
const vm = require('node:vm');
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = request.urls.map(path => {
  const url = new URL(path, 'https://example.github.io');
  const calls = [];
  const location = {pathname: url.pathname, search: url.search, hash: url.hash,
    replace: destination => calls.push(destination)};
  vm.runInNewContext(request.script, {window: {location}});
  return calls;
});
process.stdout.write(JSON.stringify(results));
"""
        def run(page, urls):
            parsed = Page((output / page).read_text())
            result = subprocess.run([NODE, "-e", runner], input=json.dumps({
                "script": "\n".join(parsed.scripts), "urls": urls,
            }), capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        self.assertEqual(run("modcam16-hk-palette/decompose.html", [
            "/modcam16-hk-palette/decompose.html?view=hdr#sample",
        ]), [["/color-picker/?view=hdr#sample"]])
        self.assertEqual(run("404.html", [
            "/modcam16-hk-palette", "/modcam16-hk-palette/",
            "/modcam16-hk-palette/index.html", "/modcam16-hk-ucs/unknown/page?x=1#demo",
            "/modcam16-hk-palette/archive/old.html", "/modcam16-hk-palette/archive/one.html",
            "/modcam16-hk-ucs-extra/", "/color-picker/", "/missing/",
        ]), [["/color-picker/"], ["/color-picker/"], ["/color-picker/"],
             ["/color-picker/?x=1#demo"], ["/perceptual-grade/"], ["/color-picker/"], [], [], []])


if __name__ == "__main__":
    unittest.main()
