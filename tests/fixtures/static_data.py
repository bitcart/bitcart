TEST_XPUB = "tpubDD5MNJWw35y3eoJA7m3kFWsyX5SaUgx2Y3AaGwFk1pjYsHvpgDwRhrStRbCGad8dYzZCkLCvbGKfPuBiG7BabswmLofb7c2yfQFhjqSjaGi"
USER_PWD = "test12345"
SUPER_USER_DATA = {
    "email": "testsuperuser@example.com",
    "password": USER_PWD,
    "is_superuser": True,
}
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
FILE_UPLOAD_ENDPOINTS = ["products"]
RANDOMIZE_TEST_XPUBS = [
    "vpub5UTue2Xx7vCNGkzLFxxyNLhH7obqaxRTE2jTUeBVN9jWsP5yz7S2yJj8t3gYK8XwGeG3sdzX2fmujuHDczzVYYw6HQB9vb6DhRfHyZke2fh",
    "vpub5URyd4soCW3dhKAPvmb6FEh8m44Q62KnzFe3UHCge6iZVrZ67aDb7JQ8QXcR9vP9qaCkXsQNfHzzqA2S2xvKfzyKSfioVtNQChfxjuPdxAt",
    "vpub5ULfj4W1KaBeQvQ3eRkhbxjcaiXnsinuqTnGfpFbb5RBc7gtUHhmYwojWMUwEuhAECGcrR75eqMWdB6jmh3HZGqBkFPgiT4KnCHiF9w3CE8",
]
PAYOUT_DESTINATION = "tb1qz28nh6ukmyumqdvysnd726f2yw77yt5ch39aga"
DEFAULT_EXPLORER = "https://blockstream.info/testnet/tx/{}"
