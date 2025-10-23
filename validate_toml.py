import toml

try:
    with open("settings.toml", "r") as f:
        data = toml.load(f)
    print("TOML file is valid")
except Exception as e:
    print(f"Error in TOML file: {e}")
