"""Render profile statistics from aggregate GitHub data only."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import subprocess

QUERY = '''query($login:String!) {
  user(login:$login) {
    login name createdAt
    repositories(privacy:PUBLIC, ownerAffiliations:OWNER) { totalCount }
    starredRepositories { totalCount }
    followers { totalCount }
    contributionsCollection {
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}'''


def render(user, today):
    collection = user['contributionsCollection']
    calendar = collection['contributionCalendar']
    days = [day for week in calendar['weeks'] for day in week['contributionDays']]
    total = calendar['totalContributions']
    private = collection['restrictedContributionsCount']
    if type(total) is not int or type(private) is not int or not 0 <= private <= total:
        raise ValueError('Invalid contribution counts')
    months = defaultdict(int)
    active = 0
    for day in days:
        datetime.strptime(day['date'], '%Y-%m-%d')
        count = day['contributionCount']
        if type(count) is not int or count < 0:
            raise ValueError('Invalid daily contribution count')
        months[day['date'][:7]] += count
        active += count > 0
    if sum(months.values()) != total:
        raise ValueError('Contribution calendar total does not match daily values')
    series = sorted(months.items())
    peak = max([value for _, value in series] + [1])
    points = [(430 + i * 480 / max(len(series) - 1, 1), 225 - value * 135 / peak)
              for i, (_, value) in enumerate(series)]
    line = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
    area = f'430,225 {line} {points[-1][0]:.1f},225' if points else ''
    name = escape(user['name'] or user['login'])
    joined = datetime.fromisoformat(user['createdAt'].replace('Z', '+00:00')).strftime('%b %Y')
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="480" viewBox="0 0 960 480" role="img" aria-labelledby="title desc">',
        f'<title id="title">{name} — GitHub activity</title>',
        f'<desc id="desc">{total} contributions in the last year, including {private} private contributions. Monthly activity chart and aggregate account statistics. Updated {today}.</desc>',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}.muted{fill:#8b949e}.value{fill:#e6edf3}.accent{fill:#58a6ff}</style>',
        '<rect width="960" height="480" rx="18" fill="#0d1117"/>',
        f'<text x="38" y="49" class="accent" font-size="27" font-weight="600">{name}</text>',
        '<text x="38" y="75" class="muted" font-size="13">GITHUB ACTIVITY · LAST 12 MONTHS</text>',
        f'<text x="38" y="144" class="value" font-size="49" font-weight="600">{total:,}</text>',
        '<text x="38" y="172" class="muted" font-size="17">contributions in the last year</text>',
        f'<text x="38" y="209" class="muted" font-size="15">Joined GitHub · {joined}</text>',
        '<text x="430" y="56" class="muted" font-size="13">MONTHLY CONTRIBUTIONS</text>',
    ]
    for fraction in (0, .5, 1):
        y = 225 - 135 * fraction
        parts += [f'<line x1="430" y1="{y}" x2="910" y2="{y}" stroke="#21262d"/>',
                  f'<text x="918" y="{y+4}" class="muted" font-size="10">{round(peak*fraction)}</text>']
    if points:
        parts += [f'<polygon points="{area}" fill="#1f6feb" opacity="0.22"/>',
                  f'<polyline points="{line}" fill="none" stroke="#58a6ff" stroke-width="3" stroke-linejoin="round"/>']
    for i, ((month, _), (x, _)) in enumerate(zip(series, points)):
        if i % 3 == 0 or i == len(series) - 1:
            parts.append(f'<text x="{x}" y="248" text-anchor="middle" class="muted" font-size="11">{month[2:]}</text>')
    parts.append('<line x1="38" y1="278" x2="922" y2="278" stroke="#30363d"/>')
    # Two genuine activity categories; no language inference from private code.
    circumference = 2 * 3.141592653589793 * 49
    private_arc = circumference * private / total if total else 0
    parts += [
        '<text x="38" y="312" class="accent" font-size="19" font-weight="600">Contribution mix</text>',
        '<circle cx="100" cy="383" r="49" fill="none" stroke="#58a6ff" stroke-width="18"/>',
        f'<circle cx="100" cy="383" r="49" fill="none" stroke="#3fb950" stroke-width="18" stroke-dasharray="{private_arc:.3f} {circumference:.3f}" transform="rotate(-90 100 383)"/>',
        '<rect x="176" y="349" width="10" height="10" rx="2" fill="#3fb950"/>',
        f'<text x="197" y="359" class="value" font-size="15">Private · {private:,}</text>',
        '<rect x="176" y="381" width="10" height="10" rx="2" fill="#58a6ff"/>',
        f'<text x="197" y="391" class="value" font-size="15">Public · {total-private:,}</text>',
    ]
    for x, y, label, value in [
        (430, 326, 'ACTIVE DAYS', active),
        (688, 326, 'PUBLIC REPOSITORIES', user['repositories']['totalCount']),
        (430, 398, 'PROJECTS STARRED', user['starredRepositories']['totalCount']),
        (688, 398, 'FOLLOWERS', user['followers']['totalCount']),
    ]:
        parts += [f'<text x="{x}" y="{y}" class="muted" font-size="11">{label}</text>',
                  f'<text x="{x}" y="{y+30}" class="value" font-size="27" font-weight="600">{value:,}</text>']
    parts += [f'<text x="38" y="460" class="muted" font-size="11">Updated {today} UTC · Source: GitHub</text>', '</svg>', '']
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', default='serdar-o')
    parser.add_argument('--output', default='assets/profile-stats.svg')
    args = parser.parse_args()
    response = subprocess.run(['gh', 'api', 'graphql', '-f', f'query={QUERY}',
                               '-f', f'login={args.user}'], check=True,
                              capture_output=True, text=True)
    data = json.loads(response.stdout)
    if data.get('errors') or not data.get('data', {}).get('user'):
        raise ValueError('GitHub did not return complete profile data')
    svg = render(data['data']['user'], datetime.now(timezone.utc).date().isoformat())
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg)
    print(f'Updated {target} using aggregate GitHub data.')


if __name__ == '__main__':
    main()
