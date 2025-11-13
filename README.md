# DocCompare (Next.js)

A lightweight Next.js application for comparing Microsoft Word documents. The app accepts two `.docx` files, automatically accepts tracked changes, converts them to HTML, and highlights the differences while preserving hyperlinks.

## Getting started

```bash
npm install
npm run dev
```

Visit http://localhost:3000 to use the interface.

## Comparison pipeline

1. Each uploaded `.docx` document is unpacked and its tracked changes are accepted server-side using `JSZip` and `@xmldom/xmldom`.
2. The cleaned document is converted to HTML with [`mammoth`](https://github.com/mwilliamson/mammoth.js), which keeps hyperlinks intact.
3. [`htmldiff-js`](https://www.npmjs.com/package/htmldiff-js) generates an HTML diff that highlights insertions and deletions.

## Deployment (Heroku)

Heroku automatically installs dependencies, runs the production build, and serves the application using `next start`:

- `Procfile` defines `web: npm run start -- -p $PORT`.
- `package.json` includes a `heroku-postbuild` script so the production bundle is generated during deployment.

### Buildpack configuration

The app must be deployed with the Node.js buildpack. If the Python buildpack is still attached from a previous experiment, the deploy will fail with the following error message during the build step:

```
App not compatible with buildpack: https://buildpack-registry.s3.amazonaws.com/buildpacks/heroku/python.tgz
```

To fix this, set the Node.js buildpack explicitly and remove the Python buildpack:

```bash
heroku buildpacks:set heroku/nodejs
heroku buildpacks:remove heroku/python
```

Alternatively, you can recreate the Heroku app (or use the [Heroku Dashboard](https://dashboard.heroku.com/)) so that it picks up the `buildpacks` entry defined in `app.json`:

```json
"buildpacks": [
  { "url": "heroku/nodejs" }
]
```

## Environment variables

No environment variables are required for basic usage.
