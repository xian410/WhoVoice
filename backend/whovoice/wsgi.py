"""
WSGI config for whovoice project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whovoice.settings")
application = get_wsgi_application()
