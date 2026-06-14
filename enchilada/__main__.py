import os
import yaml
import uvicorn


def main():
    path = os.environ.get("ENCHILADA_CONFIG", "config.yaml")
    with open(path) as f:
        config = yaml.safe_load(f)

    server = config.get("server", {})
    uvicorn_kwargs = dict(
        host=server.get("host", "0.0.0.0"),
        port=server.get("port", 8081),
    )
    if server.get("ssl_certfile"):
        uvicorn_kwargs["ssl_certfile"] = server["ssl_certfile"]
        uvicorn_kwargs["ssl_keyfile"] = server["ssl_keyfile"]

    uvicorn.run("enchilada.main:app", **uvicorn_kwargs)


if __name__ == "__main__":
    main()
