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
- The Node buildpack is selected automatically from `package.json`; no Python runtime file is required.

## Environment variables

No environment variables are required for basic usage.
