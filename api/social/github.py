import requests

from .base import BaseProvider


class GithubProvider(BaseProvider):
    def process_data(self, user, token):
        email_response = requests.get(
            "https://api.github.com/user/emails", headers={"Authorization": f'token {token["access_token"]}'}
        ).json()
        email = [entity["email"] for entity in email_response if entity["primary"]][0]
        return {
            "email": email,
            "sso_type": "github",
        }

    def get_configuration(self, client_id, client_secret):
        return {
            "name": "github",
            "client_id": client_id,
            "client_secret": client_secret,
            "access_token_url": "https://github.com/login/oauth/access_token",
            "access_token_params": None,
            "authorize_url": "https://github.com/login/oauth/authorize",
            "authorize_params": None,
            "api_base_url": "https://api.github.com/",
            "client_kwargs": {"scope": "user:email"},
            "userinfo_endpoint": "https://api.github.com/user",
        }
