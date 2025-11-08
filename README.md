# DocDiff

DocDiff is a Django application for comparing Microsoft Word (`.docx`) documents. It parses each document into structured paragraphs, highlights additions/deletions using `diff-match-patch`, and provides both an interactive web UI and JSON API. The project is pre-configured for Heroku deployment with SQLite storage, Whitenoise static serving, and optional PDF export via WeasyPrint.

## Features
- Upload two `.docx` files and view a side-by-side diff with word-level highlights.
- Optional normalization: ignore case, punctuation, or whitespace when comparing.
- HTMX-enhanced form for seamless interactions.
- Stores comparison history and exposes `/result/<id>/` and `/api/compare/` endpoints.
- PDF export powered by WeasyPrint (requires Aptfile dependencies on Heroku).
- Health check endpoint at `/health/`.

## Tech stack
- Django 5.x, Django REST Framework
- Tailwind CSS (compiled via CLI)
- docx2python with python-docx fallback
- diff-match-patch
- Whitenoise, Gunicorn, django-environ
- Pytest + pytest-django

## Project layout
```
docdiff/
├── manage.py
├── Procfile
├── runtime.txt
├── requirements.txt
├── Aptfile
├── .env.example
├── README.md
├── Makefile
├── pytest.ini
├── docdiff/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── compare/
│   ├── __init__.py
│   ├── apps.py
│   ├── diff_utils.py
│   ├── forms.py
│   ├── migrations/
│   │   ├── __init__.py
│   │   └── 0001_initial.py
│   ├── models.py
│   ├── serializers.py
│   ├── services.py
│   ├── templates/
│   │   └── compare/
│   │       ├── _controls.html
│   │       ├── _summary.html
│   │       ├── result.html
│   │       └── upload.html
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_services.py
│   │   └── test_views.py
│   ├── urls.py
│   └── views.py
├── media/
│   └── .gitkeep
└── staticfiles/
    └── .gitkeep
```

## Local development
1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy environment file: `cp .env.example .env`.
4. Run migrations: `python manage.py migrate`.
5. Build Tailwind assets (optional for development): `npx tailwindcss -i compare/static/src/input.css -o compare/static/dist/styles.css --watch`.
6. Start the development server: `python manage.py runserver`.

## Testing
Run the pytest suite:

```
pytest -v
```

## Tailwind build
The repository includes a placeholder `compare/static/dist/styles.css` for convenience. For production, build Tailwind CSS once:

```
npx tailwindcss -i compare/static/src/input.css -o compare/static/dist/styles.css --minify
```

## Heroku deployment
DocDiff is ready for deployment to Heroku. Ensure the following files are committed: `Procfile`, `runtime.txt`, `Aptfile`, `requirements.txt`, and the Django project.

### Buildpacks
```
heroku buildpacks:add --index 1 heroku-community/apt
heroku buildpacks:add --index 2 heroku/python
```

### One-time setup & deploy commands
```
# one-time setup
heroku create docdiff-app
heroku buildpacks:add --index 1 heroku-community/apt
heroku buildpacks:add --index 2 heroku/python
heroku config:set DJANGO_SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(50))")
heroku config:set DEBUG=False ALLOWED_HOSTS=docdiff-app.herokuapp.com
git push heroku main
heroku run python manage.py migrate
heroku run python manage.py collectstatic --noinput
heroku open
```

### Optional PDF dependencies
Heroku installs PDF dependencies defined in `Aptfile`. For local development on Debian/Ubuntu, install:

```
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libffi8 libgdk-pixbuf-2.0-0 libharfbuzz0b
```

## Environment variables
See `.env.example` for defaults. Important variables:
- `DJANGO_SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `S3_STORAGE_ENABLED` (reserved for future S3 integration)

## Quick start
```
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver
```

Deploy to Heroku once the app is configured using the commands above or via `make heroku-deploy`.
