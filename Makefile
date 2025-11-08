dev:
python manage.py runserver

test:
pytest -v

tailwind:
npx tailwindcss -i compare/static/src/input.css -o compare/static/dist/styles.css --watch

heroku-deploy:
git push heroku main
