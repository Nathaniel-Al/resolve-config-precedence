import os
from typing import Any, Dict, List

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ---------------------------------------------------------------- layers
# 1. defaults (hardcoded)
DEFAULTS: Dict[str, Any] = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# 2. config.development.yaml
YAML_TEXT = """\
debug: true
log_level: debug
api_key: key-cifj7icmu1
"""

# 3. .env file
DOTENV_TEXT = """\
APP_PORT=8733
APP_DEBUG=false
APP_LOG_LEVEL=warning
APP_API_KEY=key-iut5ei2smz
"""

# 4. OS-level environment variables (APP_* prefix). The assigned value is baked
#    in as a fallback; real APP_* variables set on the host override it.
OS_ENV_ASSIGNED = {"APP_API_KEY": "key-c05h7vfhmi"}

ALIASES = {"num_workers": "workers"}
INT_KEYS = {"port", "workers"}
TRUE_VALUES = {"true", "1", "yes", "on"}


def norm_key(key: str) -> str:
    k = key.strip().lower()
    if k.startswith("app_"):
        k = k[4:]
    return ALIASES.get(k, k)


def coerce(key: str, value: Any) -> Any:
    if key in INT_KEYS:
        try:
            return int(str(value).strip())
        except ValueError:
            return value
    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in TRUE_VALUES
    return str(value) if not isinstance(value, str) else value


def parse_pairs(text: str, sep: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or sep not in line:
            continue
        k, v = line.split(sep, 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def merge(layers: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for layer in layers:  # low -> high precedence
        for k, v in layer.items():
            nk = norm_key(k)
            result[nk] = coerce(nk, v)
    return result


# ------------------------------------------------------------------- CORS
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


@app.middleware("http")
async def add_cors(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    response = await call_next(request)
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --------------------------------------------------------------- endpoint
@app.get("/")
def root():
    return {"status": "ok", "endpoint": "/effective-config"}


@app.get("/effective-config")
def effective_config(set: List[str] = Query(default=[])):
    os_layer = dict(OS_ENV_ASSIGNED)
    os_layer.update({k: v for k, v in os.environ.items() if k.startswith("APP_")})

    cli: Dict[str, str] = {}
    for item in set:
        if "=" in item:
            k, v = item.split("=", 1)
            cli[k] = v

    cfg = merge([
        DEFAULTS,
        parse_pairs(YAML_TEXT, ":"),
        parse_pairs(DOTENV_TEXT, "="),
        os_layer,
        cli,
    ])
    cfg["api_key"] = "****"  # never expose the real secret
    return cfg


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
