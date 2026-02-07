from unittest.mock import patch

from kubeegg.models import EnvSelection
from kubeegg.prompts import prompt_missing_startup_vars
from kubeegg.util import extract_startup_vars


def test_extract_startup_vars_basic():
    startup = './server -port {{SERVER_PORT}} -name "{{SERVER_NAME}}"'
    assert extract_startup_vars(startup) == {"SERVER_PORT", "SERVER_NAME"}


def test_extract_startup_vars_complex():
    startup = (
        'export PATH="./jre64/bin:$PATH" ; '
        "./ProjectZomboid64 -port {{SERVER_PORT}} -udpport {{STEAM_PORT}} "
        '-cachedir=/home/container/.cache -servername "{{SERVER_NAME}}" '
        "-adminusername {{ADMIN_USER}} "
        '-adminpassword "{{ADMIN_PASSWORD}}"'
    )
    assert extract_startup_vars(startup) == {
        "SERVER_PORT",
        "STEAM_PORT",
        "SERVER_NAME",
        "ADMIN_USER",
        "ADMIN_PASSWORD",
    }


def test_extract_startup_vars_no_vars():
    assert extract_startup_vars("./start.sh --nogui") == set()


def test_extract_startup_vars_server_memory():
    startup = "java -Xmx{{SERVER_MEMORY}}M -jar server.jar"
    assert extract_startup_vars(startup) == {"SERVER_MEMORY"}


def test_prompt_missing_startup_vars_none_missing():
    env = [
        EnvSelection(key="SERVER_PORT", value="25565", sensitive=False),
        EnvSelection(key="SERVER_NAME", value="test", sensitive=False),
    ]
    startup = "./server -port {{SERVER_PORT}} -name {{SERVER_NAME}}"
    result = prompt_missing_startup_vars(startup, env)
    assert result == []


def test_prompt_missing_startup_vars_skips_server_memory():
    env = []
    startup = "java -Xmx{{SERVER_MEMORY}}M -jar server.jar"
    result = prompt_missing_startup_vars(startup, env)
    assert result == []


@patch("kubeegg.prompts.Confirm.ask", return_value=True)
@patch("kubeegg.prompts.Prompt.ask", return_value="myvalue")
def test_prompt_missing_startup_vars_prompts_missing(mock_prompt, mock_confirm):
    env = [
        EnvSelection(key="SERVER_PORT", value="25565", sensitive=False),
    ]
    startup = "./server -port {{SERVER_PORT}} -name {{SERVER_NAME}} -pass {{ADMIN_PASSWORD}}"
    result = prompt_missing_startup_vars(startup, env)
    keys = {e.key for e in result}
    assert keys == {"SERVER_NAME", "ADMIN_PASSWORD"}
    # ADMIN_PASSWORD contains PASS so sensitive_default is True, and Confirm returns True
    admin_pw = next(e for e in result if e.key == "ADMIN_PASSWORD")
    assert admin_pw.sensitive is True
    assert admin_pw.value == "myvalue"
    # SERVER_NAME doesn't contain sensitive tokens, but Confirm mock returns True
    server_name = next(e for e in result if e.key == "SERVER_NAME")
    assert server_name.value == "myvalue"
