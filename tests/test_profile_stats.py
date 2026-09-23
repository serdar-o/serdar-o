import copy
import unittest
import xml.etree.ElementTree as ET
from scripts.profile_stats import render

FIXTURE = {'name': 'A & B <test>', 'login': 'test', 'createdAt': '2024-12-14T18:20:49Z',
           'repositories': {'totalCount': 1}, 'starredRepositories': {'totalCount': 26},
           'followers': {'totalCount': 1}, 'contributionsCollection': {
               'restrictedContributionsCount': 2, 'contributionCalendar': {
                   'totalContributions': 3, 'weeks': [{'contributionDays': [
                       {'date': '2026-08-01', 'contributionCount': 1},
                       {'date': '2026-09-01', 'contributionCount': 2}]}]}}}


class CardTests(unittest.TestCase):
    def test_svg_escapes_names_and_reports_real_categories(self):
        svg = render(FIXTURE, '2026-09-24')
        ET.fromstring(svg)
        self.assertIn('A &amp; B &lt;test&gt;', svg)
        self.assertIn('Private · 2', svg)
        self.assertIn('Public · 1', svg)
        self.assertNotIn('nan', svg.lower())

    def test_zero_activity_renders_without_division_by_zero(self):
        data = copy.deepcopy(FIXTURE)
        data['contributionsCollection'] = {'restrictedContributionsCount': 0,
                                          'contributionCalendar': {'totalContributions': 0, 'weeks': []}}
        ET.fromstring(render(data, '2026-09-24'))

    def test_inconsistent_api_data_is_rejected(self):
        data = copy.deepcopy(FIXTURE)
        data['contributionsCollection']['contributionCalendar']['totalContributions'] = 10
        with self.assertRaises(ValueError):
            render(data, '2026-09-24')

    def test_invalid_private_count_is_rejected(self):
        data = copy.deepcopy(FIXTURE)
        data['contributionsCollection']['restrictedContributionsCount'] = 4
        with self.assertRaises(ValueError):
            render(data, '2026-09-24')
