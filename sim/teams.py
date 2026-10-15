"""Canonical club names. Every source's spelling maps to one name here; nothing downstream sees a second spelling."""
from __future__ import annotations
import csv, os, re, unicodedata
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS_CSV = os.path.join(ROOT, "data", "teams.csv")


class UnknownTeam(KeyError):
    pass


@lru_cache(maxsize=1)
def load_teams():
    with open(TEAMS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["altitude_ft"] = int(r["altitude_ft"] or 0)
        r["expansion_year"] = int(r["expansion_year"] or 0)
    return rows


def teams():
    return [r["team"] for r in load_teams()]


def conference_of():
    return {r["team"]: r["conference"] for r in load_teams()}


def code_of():
    return {r["team"]: r["code"] for r in load_teams()}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\b(fc|sc|cf|club|the|usa|mls)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Explicit aliases (normalised form -> canonical). Add a line whenever a source shows a new spelling.
_ALIASES = {
    "atlanta united": "Atlanta United", "atlanta utd": "Atlanta United", "atlanta": "Atlanta United",
    "charlotte": "Charlotte FC",
    "chicago fire": "Chicago Fire", "chicago": "Chicago Fire",
    "cincinnati": "FC Cincinnati",
    "columbus crew": "Columbus Crew", "columbus": "Columbus Crew", "columbus crew sc": "Columbus Crew",
    "d c united": "D.C. United", "dc united": "D.C. United", "washington dc united": "D.C. United", "dc utd": "D.C. United",
    "inter miami": "Inter Miami", "inter miami cf": "Inter Miami", "miami": "Inter Miami", "internacional de futbol miami": "Inter Miami",
    "montreal": "CF Montréal", "montreal impact": "CF Montréal", "cf montreal": "CF Montréal", "club de foot montreal": "CF Montréal", "de foot montreal": "CF Montréal",
    "nashville": "Nashville SC",
    "new england revolution": "New England Revolution", "new england": "New England Revolution", "new england rev": "New England Revolution",
    "new york city": "New York City FC", "nycfc": "New York City FC", "new york city fc": "New York City FC", "ny city": "New York City FC", "new york city football": "New York City FC",
    "new york red bulls": "New York Red Bulls", "ny red bulls": "New York Red Bulls", "red bulls": "New York Red Bulls", "new york rb": "New York Red Bulls", "nyrb": "New York Red Bulls", "new york red bull": "New York Red Bulls", "red bull new york": "New York Red Bulls", "rbny": "New York Red Bulls",
    "orlando city": "Orlando City", "orlando": "Orlando City",
    "philadelphia union": "Philadelphia Union", "philadelphia": "Philadelphia Union", "philly union": "Philadelphia Union",
    "toronto": "Toronto FC",
    "austin": "Austin FC",
    "colorado rapids": "Colorado Rapids", "colorado": "Colorado Rapids",
    "dallas": "FC Dallas",
    "houston dynamo": "Houston Dynamo", "houston": "Houston Dynamo",
    "la galaxy": "LA Galaxy", "los angeles galaxy": "LA Galaxy", "galaxy": "LA Galaxy",
    "lafc": "LAFC", "los angeles": "LAFC", "los angeles football club": "LAFC", "la": "LAFC",
    "minnesota united": "Minnesota United", "minnesota": "Minnesota United", "minnesota utd": "Minnesota United",
    "portland timbers": "Portland Timbers", "portland": "Portland Timbers",
    "real salt lake": "Real Salt Lake", "salt lake": "Real Salt Lake", "rsl": "Real Salt Lake",
    "san diego": "San Diego FC",
    "san jose earthquakes": "San Jose Earthquakes", "san jose": "San Jose Earthquakes", "sj earthquakes": "San Jose Earthquakes",
    "seattle sounders": "Seattle Sounders", "seattle": "Seattle Sounders",
    "sporting kansas city": "Sporting Kansas City", "sporting kc": "Sporting Kansas City", "kansas city": "Sporting Kansas City", "sporting k c": "Sporting Kansas City",
    "st louis city": "St. Louis City", "st louis": "St. Louis City", "saint louis city": "St. Louis City", "st louis city sc": "St. Louis City", "saint louis": "St. Louis City",
    "vancouver whitecaps": "Vancouver Whitecaps", "vancouver": "Vancouver Whitecaps", "vancouver whitecaps fc": "Vancouver Whitecaps",
}


@lru_cache(maxsize=1)
def _lookup():
    m = dict(_ALIASES)
    for r in load_teams():
        m[_norm(r["team"])] = r["team"]
        m[r["code"].lower()] = r["team"]
    return m


# Clubs that no longer exist but appear in history files; kept under one name so historical fits include them.
_HISTORICAL = {"chivas usa": "Chivas USA", "chivas": "Chivas USA"}


def canon(name: str, strict: bool = True, historical: bool = False) -> str | None:
    """Map any source spelling to the canonical name. Raises UnknownTeam when strict. historical=True also admits defunct clubs."""
    if historical and name is not None and _norm(str(name)) in _HISTORICAL:
        return _HISTORICAL[_norm(str(name))]
    if name is None:
        if strict:
            raise UnknownTeam(name)
        return None
    n = _norm(str(name))
    m = _lookup()
    if n in m:
        return m[n]
    # tolerate trailing qualifiers such as "Inter Miami CF (W)" or "LA Galaxy II"
    n2 = re.sub(r"\b(ii|2|w|women|reserves|u23|b)\b", " ", n).strip()
    if n2 in m:
        return m[n2]
    if strict:
        raise UnknownTeam(name)
    return None


def is_canon(name: str) -> bool:
    return name in set(teams())
