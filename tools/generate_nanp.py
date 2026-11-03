"""generate_nanp: build the nanp area code table from libphonenumber, once, at build time.

the runtime of this package is the standard library and nothing else, so a table that comes from
libphonenumber's metadata is generated here and committed as data rather than imported. this lives in
tools/ rather than src/ for that reason: src/ imports nothing outside the standard library, and a build
script that needs a pip install must not be inside it. rerun this when
the metadata is refreshed:

    pip install phonenumbers && python3 tools/generate_nanp.py

what the table can and cannot carry is the point. the north american numbering plan assigns **area
codes** to countries, territories and regions, which makes geography a numbering fact and a table
lookup. it does not assign line type: mobile, landline and voip all share one number block, so a +1
number's line type stays a carrier question no matter how good the table is. the generated file is
deliberately limited to what the plan encodes.
"""
import json
import pathlib

import phonenumbers
from phonenumbers import geocoder

OUT = pathlib.Path(__file__).resolve().parents[1] / "src/lookup/nanp.json"

# the plan's own words for each member. libphonenumber lists the regions, not their names
NAMES = {
    "US": "United States", "CA": "Canada", "PR": "Puerto Rico", "VI": "U.S. Virgin Islands",
    "GU": "Guam", "MP": "Northern Mariana Islands", "AS": "American Samoa",
    "BS": "Bahamas", "BB": "Barbados", "AI": "Anguilla", "AG": "Antigua and Barbuda",
    "KY": "Cayman Islands", "BM": "Bermuda", "GD": "Grenada", "TC": "Turks and Caicos Islands",
    "MS": "Montserrat", "KN": "Saint Kitts and Nevis", "LC": "Saint Lucia",
    "VC": "Saint Vincent and the Grenadines", "DM": "Dominica", "DO": "Dominican Republic",
    "TT": "Trinidad and Tobago", "JM": "Jamaica", "SX": "Sint Maarten", "VG": "British Virgin Islands",
}

TOLL_FREE = {"800", "833", "844", "855", "866", "877", "888"}
PREMIUM = {"900"}
# personal numbering codes in the nanp: a follow-me number rather than a line somebody answers
PERSONAL = {"500", "522", "533", "544", "566", "577", "588"}


def _classify(npa, iso, place, country_name):
    """the class the plan assigns, not the class a guess assigns.

    a code covering a whole country is the country: for every member bar the us and canada there is one
    area code and it is not a place. a code whose place is just the country's own name is the plan saying
    "national, not regional", which is how canada's non-geographic codes read.
    """
    if npa in TOLL_FREE:
        return "toll-free"
    if npa in PREMIUM:
        return "premium"
    if npa in PERSONAL:
        return "personal numbering"
    if iso not in ("US", "CA"):
        return "geographic"          # one code, one country: national rather than regional
    if not place or place == country_name:
        return "non-geographic"      # the plan's own "national, not regional" codes
    return "geographic"


def _sample(npa):
    """a number that the metadata accepts, so the area code can be read at all."""
    for nxx in range(200, 1000):
        candidate = f"+1{npa}{nxx}0000"
        number = phonenumbers.parse(candidate, None)
        if phonenumbers.is_valid_number(number):
            return number
    return None


def build():
    codes, seen = {}, {}
    for npa in range(200, 1000):
        number = _sample(f"{npa:03d}")
        if number is None:
            continue
        iso = phonenumbers.region_code_for_number(number) or None
        place = geocoder.description_for_number(number, "en") or None
        if iso is None:
            continue
        country_name = NAMES.get(iso, iso)
        # the place name is the metadata's own words and it glitches on small territories, so a code
        # that covers a whole country reports the country and only a regional code reports a place
        region = place if (iso in ("US", "CA") and place not in (None, country_name)) else country_name
        codes[f"{npa:03d}"] = {"iso": iso, "place": region,
                               "class": _classify(f"{npa:03d}", iso, place, country_name)}
        seen.setdefault(iso, []).append(f"{npa:03d}")
    table = {
        "_generated": {"by": "tools/generate_nanp.py", "from": f"libphonenumber {phonenumbers.__version__}",
                       "at": "2026-11-03",
                       "what": "area code -> country/territory, place name and area code class. line "
                               "type is not in this table because the plan does not encode it."},
        "countries": {iso: NAMES.get(iso, iso) for iso in sorted(seen)},
        "area_codes": dict(sorted(codes.items())),
    }
    return table, seen


def main():
    table, seen = build()
    OUT.write_text(json.dumps(table, indent=1, sort_keys=False) + "\n")
    print(f"{OUT} written: {len(table['area_codes'])} area codes across {len(seen)} countries")
    for iso in sorted(seen):
        print(f"  {iso:3} {NAMES.get(iso, iso):34} {len(seen[iso]):3} codes")


if __name__ == "__main__":
    main()
