"""Рисует карточку со статистикой контрибуций и кладёт её в assets/streak.svg.

Сторонние сервисы вроде streak-stats отвечают по 10 секунд, и camo — прокси,
через который GitHub тянет картинки в README, — успевает отвалиться по таймауту.
Поэтому считаем всё сами через GraphQL и коммитим готовый SVG прямо в репозиторий.
"""

import io
import json
import os
import urllib.request
from datetime import date, datetime, timedelta

USER = "Nikolai124"
OUT = "assets/streak.svg"
API = "https://api.github.com/graphql"

BG = "#141321"
STROKE = "#5A189A"
RING = "#C77DFF"
ACCENT = "#9D4EDD"
TEXT = "#FFFFFF"
MUTED = "#8B949E"

MONTHS = [
    "янв", "фев", "мар", "апр", "мая", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    createdAt
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def graphql(token, variables):
    payload = json.dumps({"query": QUERY, "variables": variables}).encode()
    request = urllib.request.Request(API, data=payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": f"{USER}-profile-readme",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    if "errors" in body:
        raise SystemExit(f"GraphQL вернул ошибку: {body['errors']}")
    return body["data"]["user"]


def collect_days(token):
    """Собирает календарь по годовым отрезкам — за один запрос GitHub больше года не отдаёт."""
    today = date.today()
    probe = graphql(token, {
        "login": USER,
        "from": f"{today.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
    })
    start = datetime.strptime(probe["createdAt"][:10], "%Y-%m-%d").date()

    days = {}
    cursor = start
    while cursor <= today:
        chunk_end = min(cursor + timedelta(days=364), today)
        data = graphql(token, {
            "login": USER,
            "from": f"{cursor.isoformat()}T00:00:00Z",
            "to": f"{chunk_end.isoformat()}T23:59:59Z",
        })
        weeks = data["contributionsCollection"]["contributionCalendar"]["weeks"]
        for week in weeks:
            for day in week["contributionDays"]:
                days[day["date"]] = day["contributionCount"]
        cursor = chunk_end + timedelta(days=1)

    return start, sorted(days.items())


def streaks(days):
    """Считает текущую и самую длинную серию. Сегодняшний пустой день серию не рвёт."""
    today = date.today().isoformat()

    best = current = 0
    best_range = current_range = (None, None)
    run = 0
    run_start = None

    for stamp, count in days:
        if count > 0:
            run = run + 1 if run_start else 1
            run_start = run_start or stamp
            if run > best:
                best, best_range = run, (run_start, stamp)
            current, current_range = run, (run_start, stamp)
        elif stamp != today:
            run, run_start = 0, None
            current, current_range = 0, (None, None)

    return current, current_range, best, best_range


def human(stamp):
    moment = stamp if isinstance(stamp, date) else datetime.strptime(stamp, "%Y-%m-%d").date()
    return f"{moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def span(bounds):
    start, end = bounds
    if not start:
        return "—"
    if start == end:
        return human(start)
    return f"{human(start)} — {human(end)}"


def column(x, value, label, sub, big=False):
    size = 42 if big else 34
    return f"""
  <g transform="translate({x}, 0)">
    <text x="0" y="74" text-anchor="middle" fill="{TEXT}" font-size="{size}" font-weight="700">{value}</text>
    <text x="0" y="104" text-anchor="middle" fill="{ACCENT}" font-size="14" font-weight="600">{label}</text>
    <text x="0" y="126" text-anchor="middle" fill="{MUTED}" font-size="11">{sub}</text>
  </g>"""


def render(total, current, current_range, best, best_range, since):
    ring = f"""
  <circle cx="247" cy="55" r="37" fill="none" stroke="{RING}" stroke-width="4" opacity="0.9"/>"""

    columns = (
        column(83, total, "Всего контрибуций", f"с {human(since)}")
        + ring
        + column(247, current, "Текущая серия", span(current_range), big=True)
        + column(412, best, "Лучшая серия", span(best_range))
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="160" viewBox="0 0 495 160" font-family="'Segoe UI', Ubuntu, sans-serif">
  <rect x="1" y="1" width="493" height="158" rx="8" fill="{BG}" stroke="{STROKE}" stroke-width="1.5"/>
  <line x1="165" y1="34" x2="165" y2="126" stroke="{STROKE}" stroke-width="1"/>
  <line x1="330" y1="34" x2="330" y2="126" stroke="{STROKE}" stroke-width="1"/>{columns}
</svg>
"""


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Нужен GITHUB_TOKEN — скрипт ходит в GraphQL")

    since, days = collect_days(token)
    total = sum(count for _, count in days)
    current, current_range, best, best_range = streaks(days)

    svg = render(total, current, current_range, best, best_range, since)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(svg)

    print(f"{OUT}: всего {total}, текущая серия {current}, лучшая {best}")


if __name__ == "__main__":
    main()
