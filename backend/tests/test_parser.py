import os
from app.services.parser_service import CodeParserService

def test_java_dummy_parsing():
    parser = CodeParserService()
    asset_path = os.path.join(os.path.dirname(__file__), "dummy_assets", "DummyController.java")
    with open(asset_path, "r", encoding="utf-8") as f:
        code = f.read()

    symbols = parser.parse_file(asset_path, code, "java")
    assert len(symbols) > 0
    names = [s["name"] for s in symbols]
    assert "DummyController" in names or "DummyController.java" in names

def test_python_dummy_parsing():
    parser = CodeParserService()
    asset_path = os.path.join(os.path.dirname(__file__), "dummy_assets", "dummy_service.py")
    with open(asset_path, "r", encoding="utf-8") as f:
        code = f.read()

    symbols = parser.parse_file(asset_path, code, "python")
    assert len(symbols) > 0
    names = [s["name"] for s in symbols]
    assert "UserService" in names or "fetch_user" in names or "dummy_service.py" in names

def test_mern_js_jsx_parsing():
    parser = CodeParserService()
    asset_path = os.path.join(os.path.dirname(__file__), "dummy_assets", "dummy_express_server.js")
    with open(asset_path, "r", encoding="utf-8") as f:
        code = f.read()

    symbols = parser.parse_file(asset_path, code, "javascript")
    assert len(symbols) > 0
    symbol_types = [s["symbol_type"] for s in symbols]
    names = [s["name"] for s in symbols]

    # Must detect model (User), routes, components or functions
    assert any(t in ("model", "route", "component", "function") for t in symbol_types)
    assert "User" in names or "UserProfile" in names or "UserCard" in names or any("router." in n for n in names)

def test_fallback_parsing():
    parser = CodeParserService()
    python_code = "class AccountManager:\n    def get_balance():\n        return 100\n"
    symbols_py = parser.parse_file("services/account.py", python_code, ".py")
    assert len(symbols_py) >= 2
    names = [s["name"] for s in symbols_py]
    assert "AccountManager" in names
    assert "get_balance" in names

    js_code = "const handler = () => { return true; };"
    symbols_mjs = parser.parse_file("utils/helper.mjs", js_code, ".mjs")
    assert len(symbols_mjs) >= 1
    assert symbols_mjs[0]["name"] == "handler"

