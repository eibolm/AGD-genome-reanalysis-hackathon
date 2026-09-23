"""Clinical text in any language -> HPO terms that exist in phenotype.hpoa.

Three stages, and the model never gets to name an identifier:

  1. extract   Claude reads the text in whatever language it is written in and returns
               phenotype mentions: the verbatim span, and an English clinical paraphrase.
  2. retrieve  Deterministic lexical search over the allowed vocabulary only
               (hpo_vocab.py). This is what produces candidate HPO IDs.
  3. choose    Claude picks one of the retrieved candidates per mention, or none. The
               response schema pins the allowed values to an enum of exactly those IDs,
               so an invented identifier is rejected by the API, not by us.

Every result is then re-checked against the vocabulary before it is returned. If a term
is not in phenotype.hpoa it does not come out of this module, whatever the model said.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import anthropic

import hpo_vocab

MODEL = os.environ.get('HPO_SCRIBE_MODEL', 'claude-opus-5')
CANDIDATES_PER_MENTION = 8

EXTRACT_SYSTEM = """\
You read clinical text and list the phenotypic abnormalities it describes.

The text may be in any language. Work in the language it is written in, then give an \
English clinical paraphrase for each finding.

For each distinct phenotypic abnormality, return:
  span     the exact substring of the input that states it, copied character for \
character, in the original language. Never translate, normalise or reword the span.
  english  a short English clinical phrase for the finding, of the kind used as a \
Human Phenotype Ontology term label. Prefer the plain clinical concept ("microcephaly", \
"short stature", "seizure") over a full sentence.
  negated  true if the text says the finding is ABSENT or was ruled out.
  certainty  "stated" if the text asserts the finding, "suspected" if it is hedged \
("possible", "suggestive of", "cannot be excluded").

Rules:
  - One entry per distinct finding. Do not merge two findings into one entry.
  - Do not infer findings the text does not state. A diagnosis name is not a phenotype: \
if the text says only "Marfan syndrome", do not list its typical features.
  - Skip normal findings, family history of others, treatments, and investigations \
that found nothing.
  - If the text describes no phenotypic abnormality, return an empty list.\
"""

CHOOSE_SYSTEM = """\
You match each clinical finding to the best Human Phenotype Ontology term from a fixed \
candidate list.

For every mention you are given numbered candidates retrieved from the ontology. Choose \
the single candidate that means the same clinical thing as the finding, and return its \
HPO id.

Rules:
  - You may only return an id that appears in that mention's candidate list, or the \
string "none".
  - Return "none" when no candidate means the same thing. A wrong term is worse than no \
term. Do not settle for a candidate that is merely related, is about a different body \
part, or is a different severity.
  - Prefer the term at the level of detail the text supports. If the text says \
"seizures" do not choose "generalized tonic-clonic seizure"; if it says "tonic-clonic \
seizures" do not choose the general "seizure".
  - Give a one-line reason naming what made the candidate match or why none did.\
"""


@dataclass
class Mention:
    span: str
    english: str
    negated: bool
    certainty: str
    candidates: list[dict] = field(default_factory=list)
    hpo_id: str | None = None
    label: str | None = None
    reason: str = ''
    rejected: str | None = None     # set when a returned id failed validation


@dataclass
class Annotation:
    text: str
    mentions: list[Mention]
    model: str
    vocabulary_release: str
    vocabulary_size: int
    annotator: str
    created_at: str
    usage: dict

    def to_dict(self) -> dict:
        d = asdict(self)
        d['mentions'] = [asdict(m) if not isinstance(m, dict) else m for m in self.mentions]
        return d


def _text_of(response) -> str:
    return next(b.text for b in response.content if b.type == 'text')


def _extract(client: anthropic.Anthropic, text: str) -> tuple[list[Mention], dict]:
    schema = {
        'type': 'object',
        'properties': {
            'mentions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'span': {'type': 'string'},
                        'english': {'type': 'string'},
                        'negated': {'type': 'boolean'},
                        'certainty': {'type': 'string', 'enum': ['stated', 'suspected']},
                    },
                    'required': ['span', 'english', 'negated', 'certainty'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['mentions'],
        'additionalProperties': False,
    }
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=EXTRACT_SYSTEM,
        messages=[{'role': 'user', 'content': text}],
        output_config={'format': {'type': 'json_schema', 'schema': schema}},
    )
    data = json.loads(_text_of(response))
    mentions = [
        Mention(span=m['span'], english=m['english'],
                negated=m['negated'], certainty=m['certainty'])
        for m in data['mentions']
    ]
    return mentions, _usage(response)


def _choose(client: anthropic.Anthropic, mentions: list[Mention],
            vocab: hpo_vocab.Vocabulary) -> dict:
    """Ask the model to pick from the retrieved candidates, and only those."""
    allowed_ids = sorted({c['hpo_id'] for m in mentions for c in m.candidates})
    if not allowed_ids:
        return {}

    lines = []
    for i, m in enumerate(mentions):
        lines.append(f'[{i}] finding: {m.english}')
        lines.append(f'    as written: {m.span}')
        if not m.candidates:
            lines.append('    candidates: (none retrieved)')
        for c in m.candidates:
            extra = '' if c['matched'] == c['label'] else f'  (synonym: {c["matched"]})'
            lines.append(f'    {c["hpo_id"]}  {c["label"]}{extra}')
        lines.append('')

    schema = {
        'type': 'object',
        'properties': {
            'choices': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'mention': {'type': 'integer'},
                        # The enum is the hard constraint: the API will not return an
                        # id outside the retrieved candidate set.
                        'hpo_id': {'type': 'string', 'enum': allowed_ids + ['none']},
                        'reason': {'type': 'string'},
                    },
                    'required': ['mention', 'hpo_id', 'reason'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['choices'],
        'additionalProperties': False,
    }
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=CHOOSE_SYSTEM,
        messages=[{'role': 'user', 'content': '\n'.join(lines)}],
        output_config={'format': {'type': 'json_schema', 'schema': schema}},
    )
    data = json.loads(_text_of(response))
    return {'choices': data['choices'], 'usage': _usage(response)}


def _usage(response) -> dict:
    u = response.usage
    return {
        'input_tokens': u.input_tokens,
        'output_tokens': u.output_tokens,
        'cache_read_input_tokens': getattr(u, 'cache_read_input_tokens', 0) or 0,
    }


def annotate(text: str, vocab: hpo_vocab.Vocabulary, annotator: str = 'unknown',
             client: anthropic.Anthropic | None = None) -> Annotation:
    client = client or anthropic.Anthropic()
    text = text.strip()
    if not text:
        raise ValueError('no input text')

    mentions, usage_a = _extract(client, text)

    for m in mentions:
        m.candidates = [
            {'hpo_id': c.hpo_id, 'label': c.label, 'score': c.score,
             'matched': c.matched, 'exact': c.exact}
            for c in vocab.search(m.english, limit=CANDIDATES_PER_MENTION)
        ]

    result = _choose(client, mentions, vocab)
    usage_b = result.get('usage', {'input_tokens': 0, 'output_tokens': 0,
                                   'cache_read_input_tokens': 0})

    for choice in result.get('choices', []):
        i = choice['mention']
        if not 0 <= i < len(mentions):
            continue
        m = mentions[i]
        m.reason = choice.get('reason', '')
        hpo_id = choice['hpo_id']
        if hpo_id == 'none':
            continue
        # Belt and braces. The schema enum should make both of these impossible;
        # they are here because "should" is not a guarantee worth shipping on.
        if not vocab.is_allowed(hpo_id):
            m.rejected = f'{hpo_id} is not in phenotype.hpoa'
            continue
        if hpo_id not in {c['hpo_id'] for c in m.candidates}:
            m.rejected = f'{hpo_id} was not among the candidates for this mention'
            continue
        m.hpo_id = hpo_id
        m.label = vocab.label_of(hpo_id)

    return Annotation(
        text=text,
        mentions=mentions,
        model=MODEL,
        vocabulary_release=vocab.release,
        vocabulary_size=len(vocab.terms),
        annotator=annotator,
        created_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        usage={
            'extract': usage_a,
            'choose': usage_b,
            'total_input_tokens': usage_a['input_tokens'] + usage_b['input_tokens'],
            'total_output_tokens': usage_a['output_tokens'] + usage_b['output_tokens'],
        },
    )


if __name__ == '__main__':
    import sys

    # The input is non-English by design; a Windows console defaults to cp1252
    # and would mangle the spans it prints back.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass

    sample = ' '.join(sys.argv[1:]) or (
        'Der 4-jährige Junge zeigt eine Mikrozephalie und Kleinwuchs. '
        'Die Eltern berichten über wiederkehrende Krampfanfälle seit dem '
        'zweiten Lebensjahr. Eine Muskelschwäche der Beine ist ausgeprägt. '
        'Ein Herzfehler wurde ausgeschlossen.'
    )
    vocab = hpo_vocab.load()
    print(f'vocabulary: {len(vocab.terms)} terms, release {vocab.release}\n')
    ann = annotate(sample, vocab, annotator=os.environ.get('USERNAME', 'cli'))
    for m in ann.mentions:
        flag = ' [NEGATED]' if m.negated else ''
        flag += '' if m.certainty == 'stated' else ' [suspected]'
        if m.hpo_id:
            print(f'{m.hpo_id}  {m.label}{flag}')
        elif m.rejected:
            print(f'REJECTED  {m.rejected}{flag}')
        else:
            print(f'no term   (from "{m.english}"){flag}')
        print(f'          span: {m.span!r}')
        if m.reason:
            print(f'          {m.reason}')
    print(f'\ntokens in/out: {ann.usage["total_input_tokens"]}/'
          f'{ann.usage["total_output_tokens"]}')
