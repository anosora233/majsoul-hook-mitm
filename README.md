# majsoul-hook-mitm

A majsoul message hook based on mitmproxy.

This project modifies and forwards data to achieve the following functionalities:

- [x] Compatible with the [assistant](https://github.com/EndlessCheng/mahjong-helper)
- [x] Local full skins
- [x] Local nickname
- [ ] Local reward chest
- [x] Random starred skins

## How to setup

To set up the project, follow these steps:

```bash
poetry install
poetry shell
# or `python mhmp`
python -m mhm
```

## Special Thanks

- [`parse.py`](https://github.com/Cryolite/majsoul-liqi-json) for protobuf JSON parsing.
- [`protocol.py`](https://github.com/Cryolite/majsoul-rpa) for protocol handling.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.
