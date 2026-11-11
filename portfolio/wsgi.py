"""
Ponto de entrada WSGI do projeto.

O servidor de produção (Gunicorn, ou o WSGI do provedor) importa
``application`` daqui para entregar as requisições ao Django.
"""

import os

from django.core.wsgi import get_wsgi_application

# setdefault: uma DJANGO_SETTINGS_MODULE já definida no ambiente prevalece.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portfolio.settings")

application = get_wsgi_application()
