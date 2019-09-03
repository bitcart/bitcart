from api import utils


def test_verify_password():
    p_hash = utils.get_password_hash("12345")
    assert isinstance(p_hash, str)
    assert utils.verify_password("12345", p_hash)

