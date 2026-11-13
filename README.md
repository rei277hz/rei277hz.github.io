# rei277hz.github.io

This checkout holds the current static publications:

- `color-picker/`: HDR Color Picker.
- `perceptual-grade/`: Perceptual Grade handbook.

Their source and Buck2 publishing commands are in
[chromaticity on GitHub](https://github.com/rei277hz/chromaticity). Those
commands build ZIPs through NativeLink and replace the corresponding local
directory here. This repository stores only the current snapshot on `main`.

## Publish a snapshot

```sh
./commit-timestamp.sh
```

The script stages all additions, edits, and deletions, replaces the current branch
with one parentless, signed-off timestamp commit, and force-pushes to its configured
upstream. An explicit `--force-with-lease` rejects the push if the remote branch
changes during the operation. Each successful run leaves one commit on the local
and remote branch. Existing local reflogs retain Git's normal recovery window.

Use `./commit-timestamp.sh --no-push` to replace local history without contacting
GitHub. Use the script for every publication; a plain `git commit` adds history.

## Manage old URLs

Edit [redirects.json](redirects.json), which maps old URL paths to current pages.
The two obsolete modCAM16 applications now lead to `/color-picker/`, including
the former palette's `/decompose.html` page.

A source path ending in `/` creates a redirect for that directory's index and
matches its nested URLs in the 404 fallback. A source path ending in `.html`
creates an exact page redirect. Targets must be existing pages in the current
site, so broken destinations and redirect loops are rejected before output is
replaced. Add an explicit `.html` entry for each known historical page that
should be served directly rather than through the fallback.

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/build_site.py
python3 -m http.server 8080 --directory _site
```

The JavaScript behavior check uses Node; set `NODE_BINARY=/path/to/node` if it
is not on `PATH`. The workflow requires Node and runs all checks.

The builder copies both publications unchanged into ignored `_site/`, adds a
landing page, and generates the redirect pages there. Obsolete URL directories
are deployment artifacts; they are not maintained or committed source directories.
Only `_site/` is uploaded, so repository scripts and configuration are not served.

Known aliases use an HTML redirect with JavaScript, a meta-refresh fallback, a
canonical link, and a clickable destination. JavaScript preserves the query
string and fragment. Unknown nested URLs under an obsolete prefix use the root
`404.html` fallback, which requires JavaScript and initially returns HTTP 404.
Unrelated missing URLs stay on the not-found page. Python's simple local server
does not automatically serve a custom 404 page; the fallback is tested separately.

GitHub Pages does not supply configurable server-side redirect rules. These are
HTML redirects, the same approach used by
[Jekyll Redirect From](https://github.com/jekyll/jekyll-redirect-from#how-it-works).
Actual HTTP 301/308 responses require a host or proxy that supports those rules.

## GitHub Pages setup

Select **Settings → Pages → Build and deployment → Source → GitHub Actions**
once. [The workflow](.github/workflows/pages.yml) tests and builds the site on
each push to `main`, then deploys its artifact. This follows GitHub's
[custom Pages workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
model and keeps generated redirect folders out of this repository.
