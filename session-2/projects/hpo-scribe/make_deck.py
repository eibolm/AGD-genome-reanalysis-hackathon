"""Generate the Challenge 6 presentation.

    pip install python-pptx
    python make_deck.py

Follows the five-slide structure and timings of
session-2/data/team-presentation-template.pdf. Kept as a script rather than a
hand-edited file so the numbers on slide 4 can be regenerated when they change --
every figure in here came from a real run and should stay that way.
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

OUT = Path(__file__).parent / 'hpo-scribe-presentation.pptx'

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.72)

INK = RGBColor(0x1A, 0x1D, 0x21)
MUTED = RGBColor(0x62, 0x6B, 0x75)
ACCENT = RGBColor(0x1B, 0x5E, 0x9F)
GOOD = RGBColor(0x1C, 0x7A, 0x4A)
WARN = RGBColor(0x8A, 0x53, 0x00)
LINE = RGBColor(0xDD, 0xE1, 0xE6)
PANEL = RGBColor(0xF4, 0xF6, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT = 'Segoe UI'


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def para(tf, text, size=18, bold=False, color=INK, space_after=6, space_before=0,
         align=PP_ALIGN.LEFT, first=False, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    p.space_before = Pt(space_before)
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = FONT
    return p


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def heading(slide, title, timing):
    tf = textbox(slide, MARGIN, Inches(0.5), Inches(9), Inches(0.7))
    para(tf, title, size=32, bold=True, first=True)
    tf2 = textbox(slide, W - MARGIN - Inches(1.6), Inches(0.62), Inches(1.6), Inches(0.4))
    para(tf2, timing, size=13, color=MUTED, align=PP_ALIGN.RIGHT, first=True)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, Inches(1.24),
                                 W - 2 * MARGIN, Pt(1.5))
    bar.fill.solid()
    bar.fill.fore_color.rgb = LINE
    bar.line.fill.background()
    bar.shadow.inherit = False


def bullet(tf, text, sub=None, size=17, space_before=9):
    p = para(tf, '•  ' + text, size=size, space_after=2, space_before=space_before)
    if sub:
        para(tf, '    ' + sub, size=13.5, color=MUTED, space_after=2)
    return p


def panel(slide, x, y, w, h, fill=PANEL):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = LINE
    shp.line.width = Pt(0.75)
    shp.adjustments[0] = 0.06
    shp.shadow.inherit = False
    return shp


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text.strip()


# ---------------------------------------------------------------- slide 1 ---
def slide_title(prs):
    s = blank(prs)
    tf = textbox(s, MARGIN, Inches(2.35), W - 2 * MARGIN, Inches(1.2))
    para(tf, 'hpo-scribe', size=58, bold=True, first=True, space_after=2)
    para(tf, 'Clinical text in any language → HPO terms that actually exist',
         size=23, color=ACCENT, space_after=0)

    tf2 = textbox(s, MARGIN, Inches(4.05), W - 2 * MARGIN, Inches(1.2))
    para(tf2, 'Challenge 6 — HPO annotation tool', size=19, color=MUTED, first=True)
    para(tf2, 'Eike Bolmer  ·  [add remaining team members]', size=17, space_before=10)

    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, Inches(5.7), Inches(1.6), Pt(3))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False

    tf3 = textbox(s, MARGIN, Inches(6.15), W - 2 * MARGIN, Inches(0.5))
    para(tf3, 'AI × Genomics Hackathon  ·  AGD Jahrestagung 2026',
         size=14, color=MUTED, first=True)
    notes(s, """
15 sec. Name, challenge, team. Do not explain the tool yet - slide 2 is the problem.

Say: "We are hpo-scribe. We took challenge 6, the HPO annotation tool."
""")


# ---------------------------------------------------------------- slide 2 ---
def slide_problem(prs):
    s = blank(prs)
    heading(s, 'The problem', '~30 sec')

    panel(s, MARGIN, Inches(1.6), W - 2 * MARGIN, Inches(1.0))
    tf = textbox(s, MARGIN + Inches(0.3), Inches(1.78), W - 2 * MARGIN - Inches(0.6),
                 Inches(0.7))
    para(tf, 'Turning a clinical letter into HPO terms is manual, English-centric, '
             'and leaves no record of why each term was chosen.',
         size=19, bold=True, color=ACCENT, first=True)

    tf = textbox(s, MARGIN, Inches(2.95), W - 2 * MARGIN, Inches(3.6))
    bullet(tf, 'A curator preparing a case for phenotype-driven analysis, with a '
               'free-text letter or vignette in front of them.',
           sub='Not "clinicians need better tools" — this is the moment the terms '
               'actually get assigned.', space_before=0)
    bullet(tf, 'Today: hpo.jax.org, one finding at a time, searched in English.',
           sub='A German or Spanish letter gets translated in the curator’s head '
               'first, and that translation is never written down.')
    bullet(tf, 'The level of detail drifts between curators and between sessions.',
           sub='Is "Krampfanfälle" HP:0001250 Seizure, or a more specific child term? '
               'Yesterday’s answer is not recorded, so today’s may differ.')
    bullet(tf, 'A term outside phenotype.hpoa is useless downstream — and nothing '
               'stops you picking one.',
           sub='11,658 of the ontology’s ~19,900 terms carry disease annotations. '
               'The rest look equally valid in a search box.')
    notes(s, """
30 sec. The bold line is the whole slide - say it, then pick at most two bullets.

If the room does not recognise this, nothing after it lands. The last bullet is the
one that sets up our design decision, so do not skip it: a valid-looking HPO term is
not necessarily a useful one.
""")


# ---------------------------------------------------------------- slide 3 ---
def slide_how(prs):
    s = blank(prs)
    heading(s, 'How we addressed it', '~1 min')

    tf = textbox(s, MARGIN, Inches(1.55), W - 2 * MARGIN, Inches(0.5))
    para(tf, 'Paste clinical text in any language; get back HPO terms guaranteed to '
             'appear in phenotype.hpoa.', size=19, bold=True, first=True)

    # pipeline
    y = Inches(2.35)
    bw, bh, gap = Inches(2.52), Inches(1.15), Inches(0.30)
    steps = [
        ('1. EXTRACT', 'Claude reads the text\nin its own language', ACCENT),
        ('2. RETRIEVE', 'Deterministic search over\n11,570 allowed terms', GOOD),
        ('3. CHOOSE', 'Claude picks from those\ncandidates — or none', ACCENT),
        ('4. VALIDATE', 'Re-checked against\nphenotype.hpoa', GOOD),
    ]
    x = MARGIN
    for label, body, col in steps:
        box = panel(s, x, y, bw, bh)
        t = textbox(s, x + Inches(0.16), y + Inches(0.14), bw - Inches(0.32),
                    bh - Inches(0.28))
        para(t, label, size=12.5, bold=True, color=col, space_after=4, first=True)
        para(t, body, size=12.5, color=INK, space_after=0)
        x += bw + gap
        if x < W - MARGIN:
            a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x - gap + Inches(0.05),
                                   y + Inches(0.46), Inches(0.2), Inches(0.22))
            a.fill.solid()
            a.fill.fore_color.rgb = MUTED
            a.line.fill.background()
            a.shadow.inherit = False

    t = textbox(s, MARGIN, Inches(3.62), W - 2 * MARGIN, Inches(0.4))
    para(t, 'spans + English paraphrase  →  candidate IDs  →  one ID or "none"  '
            '→  stored annotation', size=12.5, color=MUTED, first=True)

    panel(s, MARGIN, Inches(4.15), W - 2 * MARGIN, Inches(1.28), RGBColor(0xE8, 0xF5, 0xEE))
    t = textbox(s, MARGIN + Inches(0.3), Inches(4.34), W - 2 * MARGIN - Inches(0.6),
                Inches(1.0))
    para(t, 'The model never names an identifier.', size=18, bold=True, color=GOOD,
         first=True, space_after=5)
    para(t, 'Stage 1 returns text, not IDs. Every candidate ID comes from a vocabulary '
            'built out of phenotype.hpoa. The stage 3 response schema pins the answer to '
            'a JSON-Schema enum of exactly those candidates, so an invented term is '
            'rejected by the API itself — not by a sentence in a prompt.',
         size=14, color=INK, space_after=0)

    t = textbox(s, MARGIN, Inches(5.72), W - 2 * MARGIN, Inches(1.2))
    para(t, 'Deliberately not done:', size=14, bold=True, color=MUTED, first=True,
         space_after=3)
    para(t, 'no image annotation  ·  no embedding search  ·  no ontology-hierarchy '
            'navigation  ·  no model training', size=14, color=MUTED)
    notes(s, """
1 min. Walk the four boxes left to right, then land on the green panel - that is the
interesting engineering decision and the thing a judge will probe.

Expect: "how do you know it doesn't hallucinate a term?" The answer is that it cannot
name one. Retrieval produces the IDs; the schema enum restricts the choice to those
IDs; validation re-checks. Three layers, and the last two are redundant on purpose.

Translation happens BEFORE retrieval - the index is English, so searching it for
"Krampfanfaelle" returns nothing. Getting that order wrong builds a tool that silently
fails on every non-English input.
""")


# ---------------------------------------------------------------- slide 4 ---
def slide_result(prs):
    s = blank(prs)
    heading(s, 'The result', '~2 min')

    t = textbox(s, MARGIN, Inches(1.5), Inches(6.4), Inches(0.4))
    para(t, 'Live runs, not a mock', size=17, bold=True, color=GOOD, first=True)

    rows = [
        ('Input', 'Findings', 'Correct', 'Caught'),
        ('German, 4 sentences', '5', '5', '"Herzfehler ausgeschlossen" → negated'),
        ('Spanish, 4 sentences', '6', '6', 'hedged → suspected; ruled out → negated'),
    ]
    tbl = s.shapes.add_table(3, 4, MARGIN, Inches(2.0), Inches(7.3),
                             Inches(1.25)).table
    tbl.columns[0].width = Inches(2.2)
    tbl.columns[1].width = Inches(1.0)
    tbl.columns[2].width = Inches(1.0)
    tbl.columns[3].width = Inches(3.1)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = ''
            cell.fill.solid()
            cell.fill.fore_color.rgb = PANEL if r == 0 else WHITE
            cell.margin_left = cell.margin_right = Inches(0.08)
            p = cell.text_frame.paragraphs[0]
            run = p.add_run()
            run.text = val
            run.font.size = Pt(12 if r == 0 else 13)
            run.font.bold = (r == 0)
            run.font.name = FONT
            run.font.color.rgb = MUTED if r == 0 else INK

    t = textbox(s, MARGIN, Inches(3.5), Inches(7.3), Inches(2.6))
    bullet(t, 'Every term traced to the span that produced it, with the model’s '
              'one-line reason.', space_before=0, size=15)
    bullet(t, 'Negation and hedging preserved, not discarded — "ruled out" is a '
              'training signal.', size=15)
    bullet(t, 'Conservative where it should be: "pérdida auditiva bilateral" → '
              'Hearing impairment, dropping a modifier rather than inventing precision.',
           size=15)

    # right column: facts
    panel(s, Inches(8.35), Inches(1.95), Inches(4.25), Inches(2.5))
    t = textbox(s, Inches(8.6), Inches(2.14), Inches(3.8), Inches(2.2))
    for label, value in [('Allowed vocabulary', '11,570 terms'),
                         ('Searchable strings', '30,659 labels + synonyms'),
                         ('HPO release', '2026-09-01, pinned in every record'),
                         ('Per annotation', '~12 s  ·  ~$0.03  ·  2 model calls')]:
        para(t, label, size=11.5, color=MUTED, space_after=1,
             first=(label == 'Allowed vocabulary'))
        para(t, value, size=15, bold=True, space_after=9)

    panel(s, Inches(8.35), Inches(4.62), Inches(4.25), Inches(1.5),
          RGBColor(0xFD, 0xF3, 0xE2))
    t = textbox(s, Inches(8.6), Inches(4.8), Inches(3.8), Inches(1.2))
    para(t, 'The constraint is the annotation file,', size=13, bold=True, color=WARN,
         first=True, space_after=1)
    para(t, 'not "is this a valid ID"', size=13, bold=True, color=WARN, space_after=5)
    para(t, 'Saving HP:0000001 is refused. It is a real HPO term — the ontology root '
            '— but it is not in phenotype.hpoa.', size=12, space_after=0)

    t = textbox(s, MARGIN, Inches(6.32), W - 2 * MARGIN, Inches(0.8))
    para(t, 'Real vs. stubbed:', size=13.5, bold=True, color=MUTED, first=True,
         space_after=2)
    para(t, 'Nothing on this slide is hardcoded — every number came from a run. '
            'Not done: no gold-standard validation, and no timed comparison against '
            'hand annotation yet, so we cannot yet claim it is faster.',
         size=13.5, color=INK)
    notes(s, """
2 min. THE slide. Demo live if the server is up: paste the German sample, Ctrl+Enter,
about 12 seconds. Have a screenshot on this slide as backup - something always breaks.

>>> REPLACE the left half with a real screenshot of the GUI before presenting. <<<

Order: show it working, then the table, then the orange panel. The HP:0000001 example
is the strongest 20 seconds in the deck - a real HPO term, correctly refused, because
the constraint is the annotation file rather than ID validity.

Do not skip the last line. Claiming "faster and more consistent" without the timed
comparison is exactly the unsupported claim the rubric punishes. We have not measured
it, so we say so.
""")


# ---------------------------------------------------------------- slide 5 ---
def slide_limits(prs):
    s = blank(prs)
    heading(s, 'Limits, and working with Claude', '~45 sec')

    t = textbox(s, MARGIN, Inches(1.5), Inches(5.9), Inches(2.6))
    para(t, 'What it does not do', size=16, bold=True, color=MUTED, first=True,
         space_after=6)
    bullet(t, 'Recall is bounded by the lexical index.',
           sub='A phrasing sharing no words with any label returns no term — '
               'correctly, rather than a wrong one.', size=14.5, space_before=2)
    bullet(t, 'Choosing the level of detail is the error surface.',
           sub='Eight plausible siblings; picking the wrong specificity is the likely '
               'failure. Hence the visible reason string.', size=14.5)
    bullet(t, 'No hierarchy navigation, no measured precision or recall.',
           sub='Parent/child links are loaded but unused.', size=14.5)

    t = textbox(s, Inches(7.05), Inches(1.5), Inches(5.55), Inches(3.0))
    para(t, 'What Claude got wrong', size=16, bold=True, color=WARN, first=True,
         space_after=6)
    bullet(t, 'A silent CRLF bug — no error, no warning.',
           sub='chomp strips \\n but not \\r, so a column lookup missed and a whole '
               'block of the report rendered empty. Found only because a second '
               'implementation disagreed, byte for byte.',
           size=14.5, space_before=2)
    bullet(t, 'A stale server answering on a reused port.',
           sub='It reported "no API key" long after the key was set. The symptom '
               'pointed at credentials; the cause was SO_REUSEADDR.', size=14.5)

    panel(s, MARGIN, Inches(5.05), W - 2 * MARGIN, Inches(1.6))
    t = textbox(s, MARGIN + Inches(0.3), Inches(5.24), W - 2 * MARGIN - Inches(0.6),
                Inches(1.3))
    para(t, 'With another day', size=16, bold=True, color=ACCENT, first=True,
         space_after=5)
    para(t, '1.  A gold-standard set and a timed comparison against hand annotation '
            '— the success criterion we have not yet measured.', size=14,
         space_after=3)
    para(t, '2.  The disease-prior shortcut: when the disease is known, phenotype.hpoa '
            'already lists its expected terms.', size=14, space_after=3)
    para(t, '3.  Ontology hierarchy, so the annotator can move a level up or down from '
            'a suggestion.', size=14, space_after=0)
    notes(s, """
45 sec. Do not rush the middle column - "what did Claude get wrong" is scored directly,
and "nothing" reads as not having looked.

The CRLF one is the better story: a bug that produced no error at all, found only
because two independent implementations disagreed. The lesson we would keep is that
a second implementation is a cheap oracle.

End on item 1 of "with another day" - it names the thing we did not finish, which is
more convincing than a feature list.
""")


def main():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    for build in (slide_title, slide_problem, slide_how, slide_result, slide_limits):
        build(prs)
    prs.save(OUT)
    print(f'wrote {OUT}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)')


if __name__ == '__main__':
    main()
