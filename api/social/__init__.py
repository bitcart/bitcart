from .github import GithubProvider
from .google import GoogleProvider

available_providers = {
    "github": GithubProvider,
    "google": GoogleProvider,
}
