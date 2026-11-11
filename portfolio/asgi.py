"""
Ponto de entrada ASGI do projeto.

Servidores assíncronos (Uvicorn, Daphne) importam ``application`` daqui. O
deploy atual usa WSGI (``wsgi.py``); este arquivo é o padrão do
``startproject`` e fica para quem quiser servir por ASGI.
"""

import os

from django.core.asgi import get_asgi_application

# setdefault: uma DJANGO_SETTINGS_MODULE já definida no ambiente prevalece.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "portfolio.settings")

application = get_asgi_application()
