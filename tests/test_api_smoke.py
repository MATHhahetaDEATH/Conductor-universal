from conductor.core.kernel import Kernel
from conductor.interface.api.app import create_app


def test_core_api_smoke(tmp_path):
    kernel = Kernel(["conductor/plugins/core", "conductor/plugins"], storage_dir=str(tmp_path))
    kernel.start()
    app = create_app(kernel)
    client = app.test_client()
    try:
        assert client.get("/api/core/plugins").status_code == 401
        login = client.post("/api/user/login", json={"userName": "root", "password": "root"})
        assert login.status_code == 200
        token = login.get_json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        for path in ("/api/status", "/api/core/plugins", "/api/core/dependencies", "/api/core/topology", "/api/core/cli/info", "/api/logs/records", "/api/logs/files", "/api/logs/settings", "/api/prime_backup/status", "/api/prime_backup/list", "/api/hello_world/state", "/api/llm/providers"):
            response = client.get(path, headers=headers)
            assert response.status_code == 200, (path, response.get_json())
            assert response.get_json().get("success") is True
        assert client.post("/api/core/cli/suggest", json={"input": "!!"}, headers=headers).status_code == 200
        assert client.post("/api/core/cli/execute", json={"input": "!!status"}, headers=headers).status_code == 200
        assert client.post("/api/core/cli/execute", json={}, headers=headers).status_code == 400
        assert client.get("/api/core/plugin/files", headers=headers).status_code == 400
        assert client.get("/api/core/plugin/files?id=missing_plugin", headers=headers).status_code == 404
        assert client.get("/api/users", headers=headers).status_code == 200
    finally:
        kernel.stop()
