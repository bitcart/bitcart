from abc import abstractmethod


class BaseProvider:
    @abstractmethod
    def process_data(self, user, token):
        """Parse user data from a service

        Output should contain the following keys: email, first_name, last_name, provider

        Args:
            user (Union[dict,list]): data from the social service
            token (dict): token data from oauth2

        Returns:
            dict: user data
        """

    @abstractmethod
    def get_configuration(self) -> int:
        """Get oauth2 provider configuration for oauthlib

        Should provide required scope information to query email and profile data, as well as userinfo_endpoint

        Returns:
            dict: oauth2 provider configuration
        """
