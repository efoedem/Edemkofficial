import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'QUIZ1.settings')

# Vercel looks for 'app'
app = get_wsgi_application()