# The NexusUI site

This branch (`gh-pages`) is the project's GitHub Pages site. It holds only the
site: `index.html`, the screenshots in `assets/`, and this note. The library
itself is on `master`.

## Where it came from

`index.html` is the shared Jaeger project page, taken from the `gh-pages` branch
of Jaeger-Template: the same design, sections, styles and script as the other
Jenkins Robotics project sites. The content is NexusUI's own.

The parts of the template that describe a JaegerOS module were replaced, because
NexusUI is not one: "Built on JaegerOS", the pinned-framework diagram, and the
module-contract install step. Two footer links in the template no longer
resolved and were replaced with ones that do.

## Turning it on

GitHub → Settings → Pages → Source: **Deploy from a branch** → Branch:
`gh-pages`, folder `/ (root)` → Save. The site is then served at
`https://<owner>.github.io/<repository>/`.

## Updating it

- Edit `index.html` on this branch. All CSS and JavaScript are inline, so there
  is nothing to build.
- Keep it true to the code. One capability card per thing that ships; anything
  not built yet goes under "on deck". The README on `master` is the source for
  the wording and the measurements.
- The Python sample on the page is a complete program and was run as shown.
  Run it again if you change it.
- The screenshots in `assets/` were taken from the demo apps
  (`apps/widget_gallery`).
- If the repository is renamed or moved, update the GitHub links and the two
  `git clone` commands in `index.html`.
