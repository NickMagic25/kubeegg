from kubeegg.egg import parse_egg


def test_parse_egg_basic():
    data = {
        "name": "Example Egg",
        "description": "Test egg",
        "startup": "./start.sh",
        "docker_images": {"default": "example/image:latest"},
        "variables": [
            {
                "name": "Server Port",
                "env_variable": "SERVER_PORT",
                "default_value": "25565",
                "required": True,
            },
            {
                "name": "Optional Flag",
                "env_variable": "OPTIONAL_FLAG",
                "default_value": "false",
                "required": False,
            },
        ],
        "config": {"ports": ["25565"]},
    }
    egg = parse_egg(data)
    assert egg.name == "Example Egg"
    assert egg.docker_images["default"] == "example/image:latest"
    assert len(egg.variables) == 2
    assert egg.variables[0].env_variable == "SERVER_PORT"
    assert 25565 in egg.ports
