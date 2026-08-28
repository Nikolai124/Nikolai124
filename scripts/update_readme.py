"""Собирает блок «что делал недавно» из моих репозиториев и вставляет его в README.

Запускается из GitHub Actions по расписанию. Форки и этот репозиторий пропускаются.
"""

import io
import json
import os
import urllib.request
from datetime import datetime

USER = "Nikolai124"
COUNT = 6
README = "README.md"
START = "<!--RECENT:START-->"
END = "<!--RECENT:END-->"

MONTHS = [
    "янв", "фев", "мар", "апр", "мая", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]


def fetch_repos():
    url = f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-readme",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def pick(repos):
    own = [
        repo for repo in repos
        if not repo["fork"] and repo["name"].lower() != USER.lower()
    ]
    own.sort(key=lambda repo: repo["pushed_at"], reverse=True)
    return own[:COUNT]


def human_date(stamp):
    moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"{moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def cell(repo):
    meta = [repo["language"]] if repo["language"] else []
    meta.append(human_date(repo["pushed_at"]))
    return (
        f'<a href="{repo["html_url"]}"><b>{repo["name"]}</b></a><br/>'
        f'<sub>{" · ".join(meta)}</sub>'
    )


def render(repos):
    if not repos:
        return "<p align=\"center\"><sub>пока пусто</sub></p>"

    rows = []
    for index in range(0, len(repos), 2):
        pair = repos[index:index + 2]
        cells = "".join(f'<td valign="top" width="50%">\n\n{cell(r)}\n\n</td>' for r in pair)
        if len(pair) == 1:
            cells += '<td width="50%"></td>'
        rows.append(f"<tr>{cells}</tr>")

    table = "\n".join(rows)
    return f'<table width="100%">\n{table}\n</table>'


def main():
    block = render(pick(fetch_repos()))

    with io.open(README, encoding="utf-8") as handle:
        text = handle.read()

    head, _, rest = text.partition(START)
    _, _, tail = rest.partition(END)
    if not rest or not tail:
        raise SystemExit("В README нет маркеров RECENT:START / RECENT:END")

    updated = f"{head}{START}\n{block}\n{END}{tail}"
    if updated == text:
        print("без изменений")
        return

    with io.open(README, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    print("README обновлён")


if __name__ == "__main__":
    main()
