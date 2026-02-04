from kubeegg.fetch import github_blob_to_raw


def test_github_blob_to_raw():
    url = "https://github.com/pterodactyl/game-eggs/blob/main/minecraft/java/paper/egg-paper.json"
    expected = "https://raw.githubusercontent.com/pterodactyl/game-eggs/main/minecraft/java/paper/egg-paper.json"
    assert github_blob_to_raw(url) == expected


def test_github_blob_passthrough():
    url = "https://raw.githubusercontent.com/pterodactyl/game-eggs/main/minecraft/java/paper/egg-paper.json"
    assert github_blob_to_raw(url) == url
