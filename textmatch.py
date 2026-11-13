"""Small text helpers shared by descriptions.py and images.py: matching a show's title against other text."""
import re
import unicodedata

# Words in a title too common to show that a text is about this show
TITLE_STOPWORDS = {
    'exhibition', 'exhibitions', 'gallery', 'galleries', 'museum', 'present', 'presents', 'opening', 'closing',
    'solo', 'group', 'show', 'shows', 'works', 'art', 'arts', 'contemporary', 'new', 'with', 'from', 'this',
    'that', 'the', 'and', 'for', 'into', 'about', 'untitled',
}


def fold(text):
    """Lower case without accents."""
    return unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode().lower()


def title_words(name):
    """The words of a title that would show a text is about it: 4+ letters, not a stop word."""
    return {w for w in re.findall(r'[a-z0-9]{4,}', fold(name)) if w not in TITLE_STOPWORDS}
