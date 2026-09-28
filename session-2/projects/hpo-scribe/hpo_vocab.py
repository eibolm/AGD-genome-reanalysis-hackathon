"""The allowed vocabulary, and lexical search restricted to it.

The tool may only ever emit HPO terms that appear in `phenotype.hpoa`. That guarantee
lives here, not in a prompt: the vocabulary is built from the annotation file, the search
index is built only from those terms, and `is_allowed()` is the gate everything passes
through. A model can suggest whatever it likes; nothing leaves this module unless it is
in the set.

Standard library only.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent / 'data'
HPOA = DATA / 'phenotype.hpoa'
HPJSON = DATA / 'hp.json'
CACHE = DATA / 'vocab_cache.json'

# phenotype.hpoa aspects: P phenotypic abnormality, I inheritance, C clinical course,
# M clinical modifier, H past medical history. Only P is a phenotype in the sense this
# tool means, so it is the default; pass aspects=None to allow the whole file.
PHENOTYPE_ASPECTS = frozenset({'P'})

_WORD = re.compile(r'[^a-z0-9]+')


def normalize(s: str) -> str:
    """Casefold, strip accents, reduce to space-separated alphanumeric tokens.

    Accent stripping matters because the input text can be in any language and term
    labels arrive from several curation sources.
    """
    s = unicodedata.normalize('NFKD', s.casefold())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return _WORD.sub(' ', s).strip()


@dataclass(frozen=True)
class Term:
    hpo_id: str
    label: str
    synonyms: tuple[str, ...]
    n_diseases: int          # how many diseases in phenotype.hpoa carry this term

    @property
    def strings(self) -> tuple[str, ...]:
        return (self.label,) + self.synonyms


@dataclass(frozen=True)
class Candidate:
    hpo_id: str
    label: str
    score: float
    matched: str             # the label or synonym that actually matched
    exact: bool


class Vocabulary:
    """HPO terms that appear in phenotype.hpoa, plus a lexical index over them."""

    def __init__(self, terms: dict[str, Term], release: str):
        self.terms = terms
        self.release = release
        self._index: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self._strings: dict[tuple[str, int], str] = {}
        self._exact: dict[str, list[str]] = defaultdict(list)
        self._idf: dict[str, float] = {}
        self._build_index()

    # -- construction --------------------------------------------------------
    def _build_index(self) -> None:
        df: dict[str, int] = defaultdict(int)
        n_strings = 0
        for hpo_id, term in self.terms.items():
            for i, raw in enumerate(term.strings):
                norm = normalize(raw)
                if not norm:
                    continue
                n_strings += 1
                key = (hpo_id, i)
                self._strings[key] = norm
                self._exact[norm].append(hpo_id)
                seen = set()
                for tok in norm.split():
                    if tok in seen:
                        continue
                    seen.add(tok)
                    self._index[tok].append(key)
                    df[tok] += 1
        self._idf = {
            tok: math.log(1 + n_strings / count) for tok, count in df.items()
        }
        self._n_strings = n_strings

    # -- the gate ------------------------------------------------------------
    def is_allowed(self, hpo_id: str) -> bool:
        return hpo_id in self.terms

    def label_of(self, hpo_id: str) -> str | None:
        term = self.terms.get(hpo_id)
        return term.label if term else None

    # -- search --------------------------------------------------------------
    def search(self, query: str, limit: int = 8) -> list[Candidate]:
        """IDF-weighted token overlap against every label and synonym in the vocabulary.

        Deliberately boring: a deterministic, inspectable ranking that the same input
        always produces. The model's job is to choose among what this returns, never to
        supply an identifier of its own.
        """
        norm = normalize(query)
        if not norm:
            return []
        q_tokens = norm.split()
        q_set = set(q_tokens)
        q_weight = sum(self._idf.get(t, 0.0) for t in q_set) or 1.0

        scores: dict[tuple[str, int], float] = defaultdict(float)
        for tok in q_set:
            for key in self._index.get(tok, ()):
                scores[key] += self._idf.get(tok, 0.0)

        ranked: dict[str, Candidate] = {}
        for key, overlap in scores.items():
            hpo_id, _ = key
            cand_norm = self._strings[key]
            cand_tokens = cand_norm.split()
            # Recall against the query, tempered by how much of the candidate is
            # unmatched, so "seizure" does not outrank "seizure" by matching
            # "generalized tonic-clonic seizure on awakening".
            recall = overlap / q_weight
            cand_weight = sum(self._idf.get(t, 0.0) for t in set(cand_tokens)) or 1.0
            precision = overlap / cand_weight
            score = (2 * recall * precision) / (recall + precision) if overlap else 0.0
            if cand_norm == norm:
                score += 1.0
            elif q_set == set(cand_tokens):
                score += 0.25
            prev = ranked.get(hpo_id)
            if prev is None or score > prev.score:
                term = self.terms[hpo_id]
                ranked[hpo_id] = Candidate(
                    hpo_id=hpo_id,
                    label=term.label,
                    score=round(score, 4),
                    matched=term.strings[key[1]],
                    exact=(cand_norm == norm),
                )

        out = sorted(
            ranked.values(),
            key=lambda c: (-c.score, -self.terms[c.hpo_id].n_diseases, c.hpo_id),
        )
        return out[:limit]


# -- loading -----------------------------------------------------------------
def _read_hpoa(aspects: frozenset[str] | None) -> tuple[dict[str, int], str, str]:
    """Distinct HPO IDs in phenotype.hpoa and how many diseases carry each."""
    if not HPOA.exists():
        raise SystemExit(f'missing {HPOA} - see data/README.md for the download')
    counts: dict[str, int] = defaultdict(int)
    release = 'unknown'
    built_against = 'unknown'
    with HPOA.open(encoding='utf-8') as fh:
        for line in fh:
            if line.startswith('#'):
                if line.startswith('#version:'):
                    release = line.split(':', 1)[1].strip()
                elif line.startswith('#hpo-version:'):
                    # The ontology release this annotation file was curated against --
                    # the thing worth comparing hp.json to, not the hpoa build date.
                    built_against = line.split(':', 1)[1].strip()
                continue
            f = line.rstrip('\n').split('\t')
            if len(f) < 11 or f[0] == 'database_id':
                continue
            # f[2] is the qualifier: "NOT" means the disease explicitly lacks the
            # feature. Those terms are still real HPO terms and stay in the vocabulary.
            if aspects is not None and f[10] not in aspects:
                continue
            counts[f[3]] += 1
    return dict(counts), release, built_against


def _read_ontology(allowed: set[str]) -> tuple[dict[str, tuple[str, list[str]]], str]:
    if not HPJSON.exists():
        raise SystemExit(f'missing {HPJSON} - see data/README.md for the download')
    with HPJSON.open(encoding='utf-8') as fh:
        graph = json.load(fh)['graphs'][0]
    release = graph.get('meta', {}).get('version', 'unknown')
    out: dict[str, tuple[str, list[str]]] = {}
    for node in graph['nodes']:
        if node.get('type') != 'CLASS':
            continue
        m = re.search(r'HP_(\d{7})$', node['id'])
        if not m:
            continue
        hpo_id = 'HP:' + m.group(1)
        if hpo_id not in allowed:
            continue
        meta = node.get('meta', {})
        if meta.get('deprecated'):
            continue
        label = node.get('lbl')
        if not label:
            continue
        syns = [s['val'] for s in meta.get('synonyms', []) if s.get('val')]
        out[hpo_id] = (label, syns)
    return out, release


def load(aspects: frozenset[str] | None = PHENOTYPE_ASPECTS, use_cache: bool = True) -> Vocabulary:
    key = ','.join(sorted(aspects)) if aspects else 'all'
    if use_cache and CACHE.exists():
        try:
            blob = json.loads(CACHE.read_text(encoding='utf-8'))
            if blob.get('aspects') == key:
                terms = {
                    hid: Term(hid, lbl, tuple(syns), n)
                    for hid, (lbl, syns, n) in blob['terms'].items()
                }
                return Vocabulary(terms, blob['release'])
        except (ValueError, KeyError, TypeError):
            pass    # a stale or truncated cache is rebuilt, never trusted

    counts, hpoa_release, built_against = _read_hpoa(aspects)
    onto, onto_release = _read_ontology(set(counts))
    # Both are PURLs of the form .../releases/YYYY-MM-DD/hp.json when known.
    if 'unknown' not in (built_against, onto_release) and built_against != onto_release:
        print(f'warning: phenotype.hpoa was curated against {built_against} but hp.json '
              f'is {onto_release} - term IDs may have been obsoleted between releases')
    missing = set(counts) - set(onto)
    if missing:
        print(f'warning: {len(missing)} annotated terms are absent or deprecated in '
              f'hp.json and were dropped from the vocabulary')

    terms = {
        hid: Term(hid, onto[hid][0], tuple(onto[hid][1]), counts[hid])
        for hid in onto
    }
    release = f'{hpoa_release} (hpoa) / {onto_release.rsplit("/", 2)[-2] if "/" in onto_release else onto_release} (hp.json)'

    if use_cache:
        CACHE.write_text(json.dumps({
            'aspects': key,
            'release': release,
            'terms': {t.hpo_id: [t.label, list(t.synonyms), t.n_diseases]
                      for t in terms.values()},
        }), encoding='utf-8')

    return Vocabulary(terms, release)


if __name__ == '__main__':
    import sys
    import time

    t0 = time.time()
    vocab = load()
    print(f'{len(vocab.terms)} allowed terms, {vocab._n_strings} searchable strings, '
          f'release {vocab.release}, loaded in {time.time() - t0:.2f}s')
    for query in sys.argv[1:] or ['seizures', 'small head', 'short stature',
                                  'muscle weakness', 'cafe au lait spots']:
        print(f'\n{query!r}')
        for c in vocab.search(query, limit=4):
            mark = '=' if c.exact else ' '
            extra = '' if c.matched == c.label else f'  <- "{c.matched}"'
            print(f'  {mark} {c.score:5.3f}  {c.hpo_id}  {c.label}{extra}')
