TEST_XPUB = "tpubDD5MNJWw35y3eoJA7m3kFWsyX5SaUgx2Y3AaGwFk1pjYsHvpgDwRhrStRbCGad8dYzZCkLCvbGKfPuBiG7BabswmLofb7c2yfQFhjqSjaGi"
USER_PWD = "test12345"
LIMITED_USER_DATA = {
    "email": "testauthlimited@example.com",
    "password": USER_PWD,
    "is_superuser": False,
}
POLICY_USER = {
    "email": "test@test.com",
    "password": "test",
}
SCRIPT_SETTINGS = {
    "mode": "Manual",
    "domain_settings": {"domain": "bitcartcc.com", "https": True},
    "coins": {"btc": {"network": "testnet", "lightning": True}},
    "additional_services": ["tor"],
    "advanced_settings": {"additional_components": ["custom"]},
}
FALLBACK_SERVER_SETTINGS = {
    "domain_settings": {"domain": "", "https": True},
    "coins": {},
    "additional_services": [],
    "advanced_settings": {
        "installation_pack": "all",
        "bitcart_docker_repository": "",
        "additional_components": [],
    },
}
