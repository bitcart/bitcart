from api import settings

from .base import BaseProvider


class GoogleProvider(BaseProvider):
    def process_data(self, user, token):
        return {
            "email": user["email"],
            "sso_type": "google",
        }

    def get_configuration(self):
        return {
            "name": "google",
            "client_id": settings.settings.google_client_id,
            "client_secret": settings.settings.google_client_secret,
            "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
            "client_kwargs": {
                "scope": "openid email profile",
                "redirect_url": "/auth/google",
            },
        }
