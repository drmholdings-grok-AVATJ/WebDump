# WebDump

**A Python CLI for saving a website for offline viewing.**
Fetches a page's HTML plus the assets it references (`<link>`, `<script>`, `<img>`), optionally crawls same-domain links, rewrites asset paths to local files, and can serve the result locally.

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white&style=for-the-badge)](https://www.python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-green.svg?style=for-the-badge)](https://www.gnu.org/licenses/gpl-3.0)
[![Code size](https://img.shields.io/github/languages/code-size/Alangopro/WebDump?style=for-the-badge)](#)

[![GitHub stars](https://img.shields.io/github/stars/Alangopro/WebDump?style=for-the-badge)](https://github.com/Alangopro/WebDump/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Alangopro/WebDump?style=for-the-badge)](https://github.com/Alangopro/WebDump/network/members)
[![GitHub issues](https://img.shields.io/github/issues/Alangopro/WebDump?style=for-the-badge)](https://github.com/Alangopro/WebDump/issues)
[![Contributions](https://img.shields.io/badge/contributions-open-brightgreen.svg?style=for-the-badge)](https://github.com/Alangopro/WebDump/issues)


[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://dc.queenmc.pl/)
[![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://feds.lol/Kamerzystanasyt)
[![Telegram](https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://feds.lol/Kamerzystanasyt)

## Features

| Feature                     | Description                                                                 |
|------------------------------|------------------------------------------------------------------------------|
| `--recursive` / `--depth`    | follows same-domain `<a>` links up to N levels deep (default: off, i.e. single page) |
| `--max-pages`                | hard cap on total pages crawled, default 50, so a recursive run can't run away |
| `--threads`                  | assets on a page are downloaded concurrently via a thread pool (default: 20) |
| `--delay`                    | pause before each request, applied per worker thread                        |
| `--castify`                  | rewrites downloaded assets' `href`/`src` to local paths                      |
| `--beautify` (`--bf`)        | pretty-prints saved HTML (`BeautifulSoup.prettify()`); does not touch CSS/JS |
| `--minify`                   | strips HTML comments/whitespace, minifies `.css`/`.js` (needs `rcssmin`/`rjsmin`), and re-compresses images (needs `Pillow`) — silently skips a transform and warns once if its library isn't installed |
| `--nosocal`                  | strips external `<a>` links from saved pages                                |
| `--antifont`                 | deletes downloaded font files (`.woff`, `.woff2`, `.ttf`, `.otf`)            |
| `--serve` (`--autohost`)     | serves the downloaded folder locally via `http.server`                      |
| `-o, --output`               | output directory (default: domain name)                                     |
| `-q, --quiet`                | suppresses the startup banner and progress output                          |

Runs on Windows, macOS, and Linux — the `mode con` console-sizing call is now
gated behind `os.name == "nt"`. Dependencies: `requests`, `beautifulsoup4`,
`pyfiglet`, `colorama` are required; `rcssmin`, `rjsmin`, and `Pillow` are
optional and only needed for `--minify`. Install everything with
`pip install -r requirements.txt`.

## Preview

![WebDump in action](https://github.com/user-attachments/assets/39c31fb7-9880-4913-9c7f-83e80a2962e7)

## Usage

```bash
pip install -r requirements.txt
python WDumper.py <url> [options]
```

| Option                  | Description                                            |
|--------------------------|--------------------------------------------------------|
| `-o, --output`           | Output directory (default: domain name)                |
| `--recursive`            | Follow same-domain page links                           |
| `--depth`                | Max recursion depth with `--recursive` (default: 1)    |
| `--max-pages`            | Safety cap on total pages crawled (default: 50)         |
| `--serve`                | Start a local server after downloading                  |
| `--port`                 | Port for `--serve` (default: 8000)                       |
| `--castify`              | Rewrite asset links to local paths                       |
| `--beautify`             | Pretty-print saved HTML                                  |
| `--minify`               | Minify HTML/CSS/JS and re-compress images                |
| `--nosocal`              | Remove links to other domains                            |
| `--antifont`             | Remove downloaded font files                              |
| `--threads`              | Concurrent asset downloads (default: 20)                 |
| `--delay`                | Delay in seconds before each request                     |
| `--timeout`              | Request timeout in seconds (default: 30)                 |
| `-q, --quiet`            | Suppress the banner and progress output                  |

Full help:
```bash
python WDumper.py --help
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.  
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines (coming soon).


This project is licensed under the **GNU General Public License v3.0** see the [LICENSE](LICENSE) file for details.

---
