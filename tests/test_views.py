from typing import Dict, List, Union

from starlette.testclient import TestClient


class ViewTestMixin:
    """Base class for all modelview tests, as they mostly don't differ

    You must set some parameters unset in this class for it to work in your subclass
    """

    status_mapping: Dict[Union[str, bool], int] = {
        "good": 200,
        "bad": 422,
        "not found": 404,
        True: 200,
        False: 422,
    }
    name: str  # name used in endpoints
    tests: Dict[str, List[dict]]
    """dict with keys corresponding to testing function, each key is a list of
    dicts, where each dict must have status key, return_data key if status
    is good, obj_id if function requires it, and data if function sends it
    """

    def process_resp(self, resp, test):
        to_check = self.status_mapping[test["status"]]
        assert resp.status_code == to_check
        if to_check == 200:
            assert resp.json() == test["return_data"]

    def test_create(self, client: TestClient):
        for test in self.tests["create"]:
            resp = client.post(f"/{self.name}", json=test["data"])
            self.process_resp(resp, test)

    def test_get_all(self, client: TestClient):
        for test in self.tests["get_all"]:
            resp = client.get(f"/{self.name}")
            self.process_resp(resp, test)

    def test_get_one(self, client: TestClient):
        for test in self.tests["get_one"]:
            resp = client.get(f"/{self.name}/{test['obj_id']}")
            self.process_resp(resp, test)

    def test_partial_update(self, client: TestClient):
        for test in self.tests["partial_update"]:
            resp = client.patch(f"/users/{test['obj_id']}", json=test["data"])
            self.process_resp(resp, test)

    def test_full_update(self, client: TestClient):
        for test in self.tests["full_update"]:
            resp = client.put(f"/users/{test['obj_id']}", json=test["data"])
            self.process_resp(resp, test)

    def test_delete(self, client: TestClient):
        for test in self.tests["delete"]:
            resp = client.delete(f"/users/{test['obj_id']}")
            self.process_resp(resp, test)
        """assert client.delete("/users/2").status_code == 404
        resp = client.delete("/users/1")
        assert resp.status_code == 200
        assert resp.json() == {
            "email": None,
            "username": "test",
            "id": 1}
        assert client.get("/users").json() == []
        assert client.get("/users/1").status_code == 404"""


class TestUser(ViewTestMixin):
    name = "users"
    tests = {
        "create": [
            {
                "data": {"username": "test", "password": 12345},
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
            {"data": {}, "status": "bad"},
            {"data": {"username": "test"}, "status": "bad"},
            {"data": {"password": "test"}, "status": "bad"},
        ],
        "get_all": [
            {
                "status": "good",
                "return_data": [{"email": None, "username": "test", "id": 1}],
            }
        ],
        "get_one": [
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
            {"obj_id": "x", "status": "bad"},
            {"obj_id": 2, "status": "not found"},
        ],
        "partial_update": [
            {
                "obj_id": 1,
                "data": {"username": "test1"},
                "status": "good",
                "return_data": {"email": None, "username": "test1", "id": 1},
            },
            {
                "obj_id": 1,
                "data": {"username": "test1", "email": "test@example.com"},
                "status": "good",
                "return_data": {
                    "email": "test@example.com",
                    "username": "test1",
                    "id": 1,
                },
            },
            {
                "obj_id": 1,
                "data": {"username": "test1", "email": "test"},
                "status": "bad",
            },
        ],
        "full_update": [
            {"obj_id": 1, "data": {"username": "test"}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None, "username": "test"}, "status": "bad"},
            {
                "obj_id": 1,
                "data": {"id": 1, "username": "test"},
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
        ],
        "delete": [
            {"obj_id": 2, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
            {"obj_id": 1, "status": "not found"},
        ],
    }


def test_no_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 404
