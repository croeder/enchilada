import os
import yaml
import uvicorn


def main():
    path = os.environ.get("ENCHILADA_CONFIG", "config.yaml")
    with open(path) as f:
        config = yaml.safe_load(f)

    server = config.get("server", {})
    uvicorn.run(
        "enchilada.main:app",
        host=server.get("host", "0.0.0.0"),
        port=server.get("port", 8081),
    )


if __name__ == "__main__":
    main()
