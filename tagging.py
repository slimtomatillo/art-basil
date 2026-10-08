"""Subject tags (medium and theme) derived from an event's title and description.

Scrapers only know an event's type, phase and venue kind (exhibition, museum,
gallery); this adds what the show is *about* - photography, ceramics, an
indigenous artist's work - so visitors can filter by it. `process_event` calls
`add_content_tags` on every event, so every scraper (and `submissions.py`) gets
it without doing anything.

It only ever adds tags: tags a scraper or a person put on an event are never
removed. The venue's own name is blanked out of the text first, otherwise every
Asian Art Museum event would be tagged "asian". Run `python tagging.py` to apply
the current rules to everything already stored (safe to repeat), e.g. after
editing a rule.

To add a tag: draft a rule in PROPOSED, get the tag approved, then add its name
to APPROVED_TAGS and to docs/tags.html and re-run this file. Only approved tags
are ever applied. Prefer a rule that is a little too narrow over one that tags
the wrong shows - a missing tag is invisible, a wrong one is a visible error.
"""

import logging
import re

# tag -> (regex, minimum hits[, title regex]). A hit of the regex in the title
# always counts; in the description it must hit at least `minimum` times. Words
# that are often just mentioned in passing ("installation view" captions, "art,
# architecture, and archival research") need 2 or more. The optional title regex
# replaces the regex for the title only, for words that are only meaningful there
# (a "Drawing the Line" title, where the plain word "drawing" is usually a verb).
PROPOSED = {
    # --- medium
    'photography': (r"\bphotograph(s|y|er|ers|ic)?\b|\bdaguerreotype|\bphotojournalis", 1),
    'painting': (r"\bpaint(ing|ings|er|ers)\b|\boil on (canvas|panel|linen)\b|\bacrylic on\b|\bwatercolors?\b", 1),
    'sculpture': (r"\bsculpt(ure|ures|or|ors|ural)\b", 1),
    'drawing': (r"\bdrawings\b|\bcharcoal\b|\bgraphite\b|\bpen and ink\b|\bpencil\b", 1, r"\bdrawings?\b"),
    'printmaking': (r"\bprintmak|\blithograph|\bwoodcuts?\b|\bwood ?blocks?\b|\blinocuts?\b|\betching|\bengraving|\bintaglio|\baquatint|\bmezzotint|\bdrypoint|\bmonotypes?\b|\bmonoprints?\b|\bcyanotypes?\b|\bserigraph|\bsilk ?screen|\bscreen ?print|\brisograph|\bletterpress|\bchine[- ]coll|\brelief print|\bgiclee|\bgicl\u00e9e|\bprints\b", 1),
    'ceramics': (r"\bceramics?\b|\bporcelain|\bpottery|\bstoneware", 1),
    'textiles': (r"\btextiles?\b|\bquilt|\bweaving|\bweavers?\b|\bfiber art|\btapestr|\bembroider|\bknit|\bcrochet", 1),
    'installation': (r"\binstallations?\b", 2),
    'film-video': (r"\bfilms?\b|\bvideos?\b|\bmoving[- ]image|\bcinema|\bfilmmakers?\b|\bdocumentar", 2),
    'fashion': (r"\bfashion|\bcouture|\bgarments?\b|\bcostumes?\b", 1),
    'design': (r"\bdesign(s|er|ers|ed|ing)?\b", 3, r"\bdesign(s|er|ers)?\b"),
    'architecture': (r"\barchitect(s|ure|ural)?\b", 2),
    'new-media': (r"\bnew media|\bdigital (art|media|works?)\b|\binteractive\b|\bvirtual reality|\baugmented reality|\bgenerative\b|\bnet\.? ?art|\bvideo games?\b|\bsound art", 1),
    # --- theme
    'indigenous': (r"\bindigenous|\bnative american|\bnative californian|\bnative (art|artists|peoples|nations)\b|\bfirst nations|\binuit\b|\bpacific islanders?\b", 1),
    # Identity tags fire only on explicit identity language in the venue's own
    # text, never on place names or an artist's origin (see the review notes).
    'asian-american': (r"\basian[- ]american|\baapi\b|\basian diaspora|\bpacific islander", 1),
    'latinx': (r"\blatinx?\b|\blatino|\blatina|\blatine\b|\bchican", 1),
    'black-art': (r"\bblack (artists?|art|power|culture|community|communities|history|identity|spaces?|women|men|joy|life|lives)\b|\bblackness\b|\bafrican[- ]american|\bafrican diaspora|\bafrofutur", 1),
    'woman-artist': (r"\bwomen artists?\b|\bwoman artist|\bfemale artists?\b|\bfeminis|\bwomen['\u2019]s (art|work|history|voices)\b", 1),
    'queer': (r"\bqueer|\blgbtq|\btransgender|\bnon-?binary\b|\bgender[- ]?(queer|nonconforming|fluid)", 1),
}

# Only the tags listed here are ever applied, and each is also listed on
# docs/tags.html. A tag goes in only once Alex has approved it.
APPROVED_TAGS = {
    # medium
    'photography', 'painting', 'sculpture', 'printmaking', 'ceramics', 'textiles',
    'installation', 'film-video', 'fashion',
    # theme
    'indigenous', 'asian-american', 'latinx', 'black-art', 'woman-artist', 'queer',
}

def _compile(spec):
    rx, minimum, *title = spec
    return (re.compile(rx, re.IGNORECASE), minimum, re.compile(title[0], re.IGNORECASE) if title else None)

RULES = {tag: _compile(spec) for tag, spec in PROPOSED.items() if tag in APPROVED_TAGS}


def _strip_venue(text, venue):
    return re.sub(re.escape(venue), ' ', text, flags=re.IGNORECASE) if venue else text


def matches(event, rules):
    """Tags from `rules` ({tag: (regex, minimum, title regex or None)}) that apply to an event."""
    venue = event.get('venue')
    title = _strip_venue(event.get('name') or '', venue)
    description = _strip_venue(event.get('description') or '', venue)
    return [tag for tag, (rx, minimum, title_rx) in rules.items()
            if (title_rx or rx).search(title) or len(rx.findall(description)) >= minimum]


def content_tags(event):
    """The approved rule-based tags that apply to an event (existing tags not considered)."""
    return matches(event, RULES)


def add_content_tags(event):
    """Add any missing rule-based tags to event['tags']; returns True if it changed."""
    tags = event.setdefault('tags', [])
    new = [tag for tag in content_tags(event) if tag not in tags]
    tags.extend(new)
    return bool(new)


def retag_all():
    """Apply the rules to every stored event, in every region. Returns events changed."""
    from config import DB_FILES
    from utils import load_db, save_db

    changed = 0
    for region, path in DB_FILES.items():
        db = load_db(path)
        region_changed = sum(add_content_tags(event) for events in db.values() for event in events.values())
        if region_changed:
            save_db(db, region)
        logging.info(f"[{region}] tagged {region_changed} events")
        changed += region_changed
    return changed


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    print(f"{retag_all()} events gained tags")
