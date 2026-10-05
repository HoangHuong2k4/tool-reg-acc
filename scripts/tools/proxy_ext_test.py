import tempfile
import os
import shutil

def _create_proxy_extension(host, port, user, pw):
    ext_dir = tempfile.mkdtemp(prefix="proxy_ext_")
    manifest_json = """{
    "version": "1.0.0",
    "manifest_version": 2,
    "name": "Chrome Proxy",
    "permissions": [
        "proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"
    ],
    "background": { "scripts": ["background.js"] },
    "minimum_chrome_version":"22.0.0"
}"""
    background_js = f"""
    var config = {{ mode: "fixed_servers", rules: {{ singleProxy: {{ scheme: "http", host: "{host}", port: parseInt({port}) }}, bypassList: ["localhost"] }} }};
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
    function callbackFn(details) {{ return {{ authCredentials: {{ username: "{user}", password: "{pw}" }} }}; }}
    chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
    """
    with open(os.path.join(ext_dir, "manifest.json"), "w") as f: f.write(manifest_json)
    with open(os.path.join(ext_dir, "background.js"), "w") as f: f.write(background_js)
    return ext_dir
