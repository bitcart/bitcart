from .base import BaseProvider


class GoogleProvider(BaseProvider):
    def process_data(self, user, token):
        return {
            "email": user["email"],
            "sso_type": "google",
        }

    def get_configuration(self, client_id, client_secret):
        return {
            "name": "google",
            "client_id": client_id,
            "client_secret": client_secret,
            "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
            "client_kwargs": {
                "scope": "openid email profile",
                "redirect_url": "/auth/google",
            },
        }
