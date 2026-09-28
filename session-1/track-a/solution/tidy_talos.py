#!/usr/bin/env python3
"""Session 1 / Track A -- turn messy_talos_candidates.tsv into a clinician-readable summary.

    python tidy_talos.py [input.tsv] [output_dir]

Writes:
    talos_candidates_tidy.tsv   one row per unique variant, normalised columns
    talos_case_report.html      per-case review report
    talos_cleaning_log.txt      every change made to the source data

Standard library only. Output is identical to tidy_talos.pl.
"""

import os
import re
import sys
import time

IN = sys.argv[1] if len(sys.argv) > 1 else 'session-1/track-a/messy_talos_candidates.tsv'
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else 'session-1/track-a/solution'
os.makedirs(OUTDIR, exist_ok=True)

# Coordinates match GRCh38 for every row checked (e.g. RNU4-2 at 12:120291834).
# The source file carries no assembly column, so this is inferred, not declared.
ASSEMBLY = 'GRCh38'

QC = []    # data-quality notes raised while cleaning


def qc(note):
    QC.append(note)


# ---------------------------------------------------------------- helpers ---
def trim(s):
    return (s or '').strip()


def nullish(s):
    return trim(s).lower() in ('', 'missing', '.', 'na', 'nan')


def val(s):
    return None if nullish(s) else trim(s)


def to_bool(s):
    return 1 if trim(s).lower() in ('true', 'yes', 'y', '1') else 0


NUM_RE = re.compile(r'^[-+]?[0-9.]+([eE][-+]?\d+)?$')


def num(s):
    v = val(s)
    if v is None or not NUM_RE.match(v):
        return None
    return float(v)


def pnum(x):
    """Stringify a number the way Perl does, so both scripts agree (34.0 -> '34')."""
    if x is None:
        return ''
    return f'{x:.15g}'


def fmt_af(af):
    """gnomAD AFs arrive with float noise (2.499999936844688e-06); 3 sig figs is plenty."""
    if af is None:
        return 'not reported'
    if af == 0:
        return 'absent (0)'
    return f'{af:.3g}'


def iso_date(s):
    d = val(s)
    if d is None:
        return None
    if re.match(r'^\d{4}-\d{2}-\d{2}$', d):
        return d
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', d)
    if m:                                       # DD/MM/YYYY
        return '%04d-%02d-%02d' % (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return d


def norm_chrom(s):
    c = re.sub(r'(?i)^chr', '', trim(s))
    if re.match(r'(?i)^[xym]', c):
        c = c.upper()
    if c == 'M':
        c = 'MT'
    return c


GT_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]*)"')


def parse_gts(raw):
    """The genotypes column is a JSON object embedded in a TSV, so its quotes are doubled."""
    raw = trim(raw)
    raw = re.sub(r'^"', '', raw)
    raw = re.sub(r'"$', '', raw)
    raw = raw.replace('""', '"')
    return {k.lower(): v for k, v in GT_RE.findall(raw)}


CSQ_ALIAS = {
    'missense': 'missense_variant',
    'non_coding': 'non_coding_transcript_exon_variant',
}
CSQ_LABEL = {
    'frameshift_variant': 'Frameshift',
    'splice_donor_variant': 'Splice donor',
    'splice_acceptor_variant': 'Splice acceptor',
    'stop_gained': 'Stop gained (nonsense)',
    'missense_variant': 'Missense',
    'non_coding_transcript_exon_variant': 'Non-coding transcript',
}
IS_LOF = {'frameshift_variant', 'splice_donor_variant', 'splice_acceptor_variant', 'stop_gained'}


def norm_moi(s):
    m = trim(s)
    if m == '':
        return None
    low = m.lower()
    if low in ('ad', 'autosomal dominant'):
        return 'Autosomal dominant'
    if re.match(r'^ar\s*\(hom', low):
        return 'Autosomal recessive (homozygous)'
    if re.match(r'^ar\s*\(comp', low):
        return 'Autosomal recessive (compound het)'
    if re.search(r'x-?linked\s+recessive', low):
        return 'X-linked recessive'
    return m


def norm_clinvar(s):
    c = val(s)
    if c is None:
        return None
    low = c.lower()
    if low in ('p/lp', 'pathogenic/likely pathogenic'):
        return 'Pathogenic / Likely pathogenic'
    if low in ('vus', 'uncertain significance'):
        return 'Uncertain significance (VUS)'
    if low in ('b/lb', 'benign/likely benign'):
        return 'Benign / Likely benign'
    return c


AA = {'A': 'Ala', 'R': 'Arg', 'N': 'Asn', 'D': 'Asp', 'C': 'Cys', 'Q': 'Gln', 'E': 'Glu',
      'G': 'Gly', 'H': 'His', 'I': 'Ile', 'L': 'Leu', 'K': 'Lys', 'M': 'Met', 'F': 'Phe',
      'P': 'Pro', 'S': 'Ser', 'T': 'Thr', 'W': 'Trp', 'Y': 'Tyr', 'V': 'Val', 'X': 'Ter'}


def norm_hgvsp(s):
    p = val(s)
    if p is None:
        return None
    if ':p.' in p:
        p = re.sub(r'^[^:]*:', '', p)           # drop ENSP accession prefix
    p = re.sub(r'^p\.\((.+)\)$', r'p.\1', p)    # drop the "predicted" parentheses
    m = re.match(r'^p\.([A-Z])(\d+)([A-Z*])$', p)
    if m:                                       # 1-letter -> 3-letter
        a, n, b = m.groups()
        frm = AA.get(a)
        to = 'Ter' if b == '*' else AA.get(b)
        if frm and to:
            p = f'p.{frm}{n}{to}'
    return p


def norm_hgvsc(s):
    c = val(s)
    if c is None:
        return None
    if ':c.' in c:
        c = re.sub(r'^[^:]*:', '', c)
    if c.startswith('c.'):
        return c
    return None      # "135912503G>A" looks like HGVS but is not; drop it


PRED_RE = re.compile(r'^([a-zA-Z_]+)\(([^)]*)\)$')


def fmt_pred(s):
    v = val(s)
    if v is None:
        return None
    m = PRED_RE.match(v)
    if m:
        t = m.group(1).replace('_', ' ')
        return t[:1].upper() + t[1:] + f' ({m.group(2)})'
    return v


def merge_rec(v, r):
    """Identical variant reported more than once: OR the evidence flags, union the
    warnings and modes of inheritance, keep the first non-empty annotation."""
    v['rows'].append(r['row'])
    for f in ('cat1', 'cat2', 'cat3', 'denovo', 'pm5'):
        v[f] = v[f] or r[f]
    for f in ('am_class', 'am_score', 'hgvsc', 'hgvsp', 'af', 'clinvar', 'stars', 'cadd',
              'revel', 'sift', 'polyphen', 'tagged', 'tech', 'gene', 'gene_id'):
        if v[f] is None and r[f] is not None:
            v[f] = r[f]
    if len(r['panels']) > len(v['panels']):
        v['panels'] = r['panels']


# ------------------------------------------------------------------ read ----
with open(IN, encoding='utf-8') as fh:
    cols = fh.readline().rstrip('\n').split('\t')
    ix = {c: i for i, c in enumerate(cols)}

    variant = {}
    order = []
    n_rows = 0

    for line in fh:
        line = line.rstrip('\n')
        if not line.strip():
            continue
        n_rows += 1
        f = line.split('\t')

        def get(c, f=f):
            i = ix.get(c)
            return f[i] if i is not None and i < len(f) else ''

        raw_sample = get('sample_id')
        sample = trim(raw_sample).upper()
        if trim(raw_sample) != sample or raw_sample != trim(raw_sample):
            qc(f"row {n_rows}: sample_id '{raw_sample}' normalised to '{sample}'")

        raw_chrom = get('chromosome')
        chrom = norm_chrom(raw_chrom)
        if trim(raw_chrom) != chrom:
            qc(f"row {n_rows}: chromosome '{raw_chrom}' normalised to '{chrom}'")

        pos, ref, alt = trim(get('position')), trim(get('REF')), trim(get('ALT'))
        key = '|'.join([sample, chrom, pos, ref, alt])

        raw_csq = trim(get('consequence')).lower()
        csq = CSQ_ALIAS.get(raw_csq, raw_csq)
        if csq != raw_csq:
            qc(f"row {n_rows}: consequence '{raw_csq}' standardised to '{csq}'")

        # Talos category 4 (de novo) holds the sample ID it fired for, not a boolean,
        # so compare it with this row's sample rather than casting it.
        raw_c4 = trim(get('Talos_category_4')).upper()
        denovo = 1 if raw_c4 != '' and raw_c4 == sample else 0

        raw_hgvsc = val(get('MANE_HGVSc'))
        hgvsc = norm_hgvsc(get('MANE_HGVSc'))
        if raw_hgvsc is not None and hgvsc is None:
            qc(f"row {n_rows}: MANE_HGVSc '{raw_hgvsc}' is not HGVS notation and was dropped")

        raw_date = val(get('first_tagged'))
        date = iso_date(get('first_tagged'))
        if raw_date is not None and date is not None and raw_date != date:
            qc(f"row {n_rows}: first_tagged '{raw_date}' reformatted to '{date}'")

        rec = {
            'row': n_rows,
            'sample': sample,
            'gene': trim(get('gene_symbol')),
            'gene_id': trim(get('gene_id')),
            'chrom': chrom,
            'pos': pos,
            'ref': ref,
            'alt': alt,
            'cat1': to_bool(get('Talos_category_1')),
            'cat2': to_bool(get('Talos_category_2')),
            'cat3': to_bool(get('Talos_category_3')),
            'denovo': denovo,
            'pm5': to_bool(get('PM5')),
            'am_class': val(get('AlphaMissense_class')),
            'am_score': num(get('AlphaMissense_score')),
            'moi': norm_moi(get('inheritance_reason')),
            'gts': parse_gts(get('genotypes')),
            'csq': csq,
            'hgvsc': hgvsc,
            'hgvsp': norm_hgvsp(get('MANE_HGVSp')),
            'af': num(get('gnomAD_AF')),
            'clinvar': norm_clinvar(get('ClinVar')),
            'stars': num(get('ClinVar_stars')),
            'cadd': num(get('CADD')),
            'revel': num(get('REVEL')),
            'sift': fmt_pred(get('SIFT')),
            'polyphen': fmt_pred(get('PolyPhen')),
            'panels': [p for p in (trim(x) for x in trim(get('panels')).split(';')) if p],
            'tagged': date,
            'warning': val(get('warnings')),
            'tech': trim(get('extra_technical_field')),
        }

        if key not in variant:
            v = dict(rec)
            v['rows'] = [n_rows]
            v['mois'] = {}
            v['warnings'] = {}
            variant[key] = v
            order.append(key)
        else:
            merge_rec(variant[key], rec)
        v = variant[key]
        if rec['moi'] is not None:
            v['mois'][rec['moi']] = 1
        if rec['warning'] is not None:
            v['warnings'][rec['warning']] = 1

for key in order:
    v = variant[key]
    if len(v['rows']) > 1:
        qc(f"{key}: source rows {', '.join(str(r) for r in v['rows'])} "
           'describe the same variant and were merged')
        m = sorted(v['mois'])
        if len(m) > 1:
            qc(f"{key}: merged rows disagree on mode of inheritance ({' vs '.join(m)})")

# ------------------------------------------------- segregation & phasing ----
for key in order:
    v = variant[key]
    g = v['gts']
    p = (g.get('proband') or '').upper()
    m = (g.get('mother') or '').upper()
    d = (g.get('father') or '').upper()
    v['gt_string'] = f'proband {p} / mother {m} / father {d}'

    def carrier(x):
        return x in ('HET', 'HOM', 'HEMI')

    if p == 'HOM':
        v['origin'] = 'biparental'
    elif p == 'HEMI' and m == 'HET':
        v['origin'] = 'maternal'
    elif p == 'HET' and m == 'WT' and d == 'WT':
        v['origin'] = 'de novo'
    elif p == 'HET' and carrier(m) and d == 'WT':
        v['origin'] = 'maternal'
    elif p == 'HET' and carrier(d) and m == 'WT':
        v['origin'] = 'paternal'
    else:
        v['origin'] = 'unresolved'

    if v['denovo'] and v['origin'] != 'de novo':
        qc(f"{key}: Talos category 4 (de novo) is set, "
           f"but trio genotypes read {v['gt_string']}")

# Pair compound heterozygotes within a sample+gene and check they are in trans.
by_gene = {}
for key in order:
    by_gene.setdefault(variant[key]['sample'] + '|' + variant[key]['gene'], []).append(key)

PHASEABLE = ('maternal', 'paternal', 'de novo')
for grp in by_gene.values():
    if len(grp) < 2:
        continue
    for a in grp:
        partners = []
        for b in grp:
            if a == b:
                continue
            oa, ob = variant[a]['origin'], variant[b]['origin']
            if oa in PHASEABLE and ob in PHASEABLE:
                partners.append({'key': b, 'trans': 1 if oa != ob else 0})
        variant[a]['partners'] = partners

# ----------------------------------------------------------- tier & why -----
for key in order:
    v = variant[key]
    why, caveats = [], []

    plp = 1 if v['clinvar'] and v['clinvar'].startswith('Pathogenic') else 0
    lof = 1 if v['csq'] in IS_LOF else 0
    hom = 1 if v['origin'] == 'biparental' else 0
    hemi = 1 if (v['gts'].get('proband') or '').upper() == 'HEMI' else 0
    dn = 1 if v['origin'] == 'de novo' else 0
    trans = [p for p in v.get('partners', []) if p['trans']]

    if plp:
        s = 'ClinVar pathogenic / likely pathogenic'
        if v['stars'] is not None:
            s += ' (%d review star%s)' % (v['stars'], '' if v['stars'] == 1 else 's')
        why.append(s)
    if dn:
        why.append('De novo in proband (both parents wild-type)')
    if lof:
        why.append('Predicted loss of function: ' + CSQ_LABEL.get(v['csq'], v['csq']).lower())
    if hom:
        why.append('Homozygous in proband, both parents heterozygous')
    if hemi:
        why.append('Hemizygous in proband, maternally inherited')
    if trans:
        pv = variant[trans[0]['key']]
        why.append('Compound heterozygous in trans with %s:%s %s>%s (%s vs %s)'
                   % (pv['chrom'], pv['pos'], pv['ref'], pv['alt'], v['origin'], pv['origin']))
        v['comphet'] = '%s:%s %s>%s' % (pv['chrom'], pv['pos'], pv['ref'], pv['alt'])
    if v['am_class'] == 'likely_pathogenic':
        why.append('AlphaMissense %s (%.2f)' % (v['am_class'], v['am_score']))
    if v['pm5']:
        why.append('ACMG PM5 flagged by Talos')
    if v['af'] is not None and v['af'] == 0:
        why.append('Absent from gnomAD')
    if v['af'] is not None and v['af'] > 0:
        why.append('Ultra-rare in gnomAD (%s)' % fmt_af(v['af']))
    if v['cadd'] is not None and v['cadd'] >= 25:
        why.append('CADD %.1f' % v['cadd'])

    if v['am_class'] and re.search(r'benign|ambiguous', v['am_class']):
        caveats.append('AlphaMissense %s (%.2f)' % (v['am_class'], v['am_score']))
    if v['clinvar'] is None:
        caveats.append('Not present in ClinVar')
    if v['clinvar'] and 'Uncertain' in v['clinvar']:
        caveats.append('ClinVar: uncertain significance')
    if v['af'] is None:
        caveats.append('gnomAD frequency not reported')
    for w in sorted(v['warnings']):
        caveats.append(f'Talos QC warning: {w}')

    mois = sorted(v['mois'])
    if len(mois) > 1:
        caveats.append('Source rows disagree on mode of inheritance: ' + ' vs '.join(mois))
    if len(v['rows']) > 1:
        caveats.append(f"Reported in {len(v['rows'])} source rows (merged)")

    # Talos category 1 is the ClinVar-driven category; firing it with no ClinVar
    # record is a contradiction in the source data, not a finding.
    if v['cat1'] and v['clinvar'] is None:
        caveats.append('Talos category 1 set but no ClinVar record in this file')
        qc(f'{key}: Talos_category_1 is TRUE but the ClinVar column is empty/missing')

    benign = 1 if v['am_class'] == 'likely_benign' else 0
    if plp and (lof or dn or hom or hemi or trans):
        tier = 'A'
    elif plp or (dn and lof) or (trans and v['am_class'] == 'likely_pathogenic'):
        tier = 'B'
    else:
        tier = 'C'
    if benign and not plp:
        tier = 'C'

    v['why'] = why
    v['caveats'] = caveats
    v['tier'] = tier
    v['mois_l'] = mois

TIER_RANK = {'A': 0, 'B': 1, 'C': 2}
ordered = sorted(order, key=lambda k: (variant[k]['sample'],
                                       TIER_RANK[variant[k]['tier']],
                                       -(variant[k]['cadd'] or 0),
                                       variant[k]['gene']))

# ------------------------------------------------------------- output ------
def esc(s):
    if s is None:
        s = ''
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def dash(s):
    return s if s not in (None, '') else '-'


now = time.strftime('%Y-%m-%d %H:%M')

# --- tidy TSV ---------------------------------------------------------------
OUT_COLS = """sample_id tier gene_symbol gene_id assembly chrom pos ref alt variant_id
    hgvs_c hgvs_p consequence consequence_label loss_of_function
    mode_of_inheritance proband_gt mother_gt father_gt inferred_origin comphet_partner
    gnomad_af clinvar clinvar_stars cadd revel sift polyphen
    alphamissense_class alphamissense_score
    talos_cat1 talos_cat2 talos_cat3 talos_cat4_de_novo talos_pm5
    panels first_tagged talos_warnings why_prioritised caveats source_rows""".split()

yn = lambda b: 'yes' if b else 'no'

with open(os.path.join(OUTDIR, 'talos_candidates_tidy.tsv'), 'w',
          encoding='utf-8', newline='\n') as t:
    t.write('\t'.join(OUT_COLS) + '\n')
    for key in ordered:
        v = variant[key]
        row = [
            v['sample'], v['tier'], v['gene'], v['gene_id'], ASSEMBLY,
            v['chrom'], v['pos'], v['ref'], v['alt'],
            '-'.join([v['chrom'], v['pos'], v['ref'], v['alt']]),
            dash(v['hgvsc']), dash(v['hgvsp']), v['csq'],
            CSQ_LABEL.get(v['csq'], v['csq']),
            yn(v['csq'] in IS_LOF),
            '; '.join(v['mois_l']),
            (v['gts'].get('proband') or '').upper(),
            (v['gts'].get('mother') or '').upper(),
            (v['gts'].get('father') or '').upper(),
            v['origin'], dash(v.get('comphet')),
            ('%.3g' % v['af']) if v['af'] is not None else '',
            dash(v['clinvar']), pnum(v['stars']),
            pnum(v['cadd']), pnum(v['revel']),
            dash(v['sift']), dash(v['polyphen']),
            dash(v['am_class']), pnum(v['am_score']),
            yn(v['cat1']), yn(v['cat2']), yn(v['cat3']), yn(v['denovo']), yn(v['pm5']),
            '; '.join(v['panels']), dash(v['tagged']),
            '; '.join(sorted(v['warnings'])),
            ' | '.join(v['why']), ' | '.join(v['caveats']),
            ','.join(str(r) for r in v['rows']),
        ]
        t.write('\t'.join('' if c is None else str(c) for c in row) + '\n')

# --- cleaning log -----------------------------------------------------------
with open(os.path.join(OUTDIR, 'talos_cleaning_log.txt'), 'w',
          encoding='utf-8', newline='\n') as log:
    log.write('Talos candidate table -- cleaning log\n')
    log.write(f'source: {IN}\ngenerated: {now}\n')
    log.write(f'source rows: {n_rows} -> unique variants: {len(order)}\n\n')
    for note in QC:
        log.write(note + '\n')

# --- HTML report ------------------------------------------------------------
by_sample = {}
for key in ordered:
    by_sample.setdefault(variant[key]['sample'], []).append(key)

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Talos candidate review</title>
<style>
:root{
  --bg:#ffffff; --panel:#f7f8fa; --line:#dfe3e8; --ink:#1a1d21; --muted:#5b6470;
  --a:#b3261e; --a-bg:#fdeceb; --b:#8a5300; --b-bg:#fdf3e2; --c:#4a5560; --c-bg:#eef1f4;
  --accent:#1b4d8f;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#15181c; --panel:#1d2126; --line:#2f353c; --ink:#e8ebee; --muted:#9aa4b0;
    --a:#ff8a80; --a-bg:#3a1f1d; --b:#ffcc80; --b-bg:#3a2e1a; --c:#b0bac4; --c-bg:#252a30;
    --accent:#8ab4f8;
  }
}
:root[data-theme="dark"]{
  --bg:#15181c; --panel:#1d2126; --line:#2f353c; --ink:#e8ebee; --muted:#9aa4b0;
  --a:#ff8a80; --a-bg:#3a1f1d; --b:#ffcc80; --b-bg:#3a2e1a; --c:#b0bac4; --c-bg:#252a30;
  --accent:#8ab4f8;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px}
h2{font-size:1.2rem;margin:32px 0 8px;padding-top:8px;border-top:1px solid var(--line)}
h3{font-size:.95rem;margin:16px 0 6px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.sub{color:var(--muted);margin:0 0 20px;font-size:.9rem}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:6px;padding:12px 14px;margin:16px 0;font-size:.88rem}
.note p{margin:.4em 0}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:16px 0;
  position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line)}
input[type=search]{flex:1 1 240px;min-width:180px;padding:7px 10px;border:1px solid var(--line);
  border-radius:6px;background:var(--panel);color:var(--ink);font:inherit;font-size:.9rem}
.controls label{font-size:.85rem;color:var(--muted);display:flex;align-items:center;gap:4px}
button{padding:6px 12px;border:1px solid var(--line);border-radius:6px;background:var(--panel);
  color:var(--ink);font:inherit;font-size:.85rem;cursor:pointer}
button:hover{border-color:var(--accent)}
.summary{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 14px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 12px;font-size:.85rem}
.stat b{display:block;font-size:1.25rem;line-height:1.2}
table{width:100%;border-collapse:collapse;font-size:.87rem}
th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);
  cursor:pointer;user-select:none;white-space:nowrap}
th:hover{color:var(--accent)}
tbody.cand>tr.main{cursor:pointer}
tbody.cand:hover>tr.main{background:var(--panel)}
tbody.cand.open>tr.main{background:var(--panel)}
.tier{display:inline-block;min-width:1.5em;text-align:center;font-weight:700;
  border-radius:4px;padding:1px 6px;font-size:.8rem}
.tier.A{color:var(--a);background:var(--a-bg)}
.tier.B{color:var(--b);background:var(--b-bg)}
.tier.C{color:var(--c);background:var(--c-bg)}
.gene{font-weight:600}
.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.82rem}
.muted{color:var(--muted)}
.chip{display:inline-block;border:1px solid var(--line);border-radius:10px;
  padding:0 7px;margin:1px 3px 1px 0;font-size:.74rem;background:var(--panel);white-space:nowrap}
.detail{display:none}
tbody.cand.open .detail{display:table-row}
.detail td{background:var(--panel);padding:14px 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:18px}
ul.why{margin:4px 0;padding-left:18px}
ul.why li{margin:2px 0}
ul.why.cav li{color:var(--muted)}
dl{margin:4px 0;display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:.84rem}
dt{color:var(--muted)}
dd{margin:0}
a{color:var(--accent)}
.links a{margin-right:10px;font-size:.82rem;white-space:nowrap}
.foot{margin-top:40px;padding-top:12px;border-top:1px solid var(--line);
  font-size:.8rem;color:var(--muted)}
.foot code{font-size:.95em}
@media (max-width:720px){
  .wrap{padding:16px}
  table{font-size:.8rem}
  th,td{padding:6px 5px}
  .hide-sm{display:none}
}
@media print{
  .controls,.no-print{display:none}
  .detail{display:table-row !important}
  body{background:#fff;color:#000}
  tbody.cand{break-inside:avoid}
}
</style>
</head>
<body>
<div class="wrap">
<h1>Talos candidate review</h1>
<p class="sub">Source: <span class="mono">__IN__</span> &middot; __NROWS__ source rows condensed to
__NVAR__ unique variants across __NCASE__ cases &middot;
coordinates interpreted as __ASSEMBLY__ &middot; generated __NOW__</p>

<div class="note no-print">
<p><b>How to read this.</b> One row per unique variant per case, ordered by review tier.
Click any row to open the full evidence, in-silico scores and external links.
Every tier is derived from the fields in the source file and is spelled out under
<i>Why prioritised</i> &mdash; there is no hidden score.</p>
<p><b>Tier A</b> ClinVar pathogenic/likely pathogenic <i>and</i> a supporting genotype
(loss of function, de novo, homozygous, hemizygous, or compound heterozygous in trans).
<b>Tier B</b> one strong line of evidence without the other.
<b>Tier C</b> everything else, including variants predicted benign &mdash; review, but not first.</p>
<p><b>Not a clinical report.</b> Synthetic workshop data derived from the public Talos
test fixture. No patient data. Nothing here is a clinical interpretation.</p>
</div>

<div class="controls no-print">
<input type="search" id="q" placeholder="Filter by gene, variant, consequence, inheritance...">
<label><input type="checkbox" class="tf" value="A" checked> A</label>
<label><input type="checkbox" class="tf" value="B" checked> B</label>
<label><input type="checkbox" class="tf" value="C" checked> C</label>
<button id="expand">Expand all</button>
<button id="collapse">Collapse all</button>
<button id="theme">Toggle theme</button>
</div>
"""

H = [HEAD.replace('__IN__', IN).replace('__NROWS__', str(n_rows))
         .replace('__NVAR__', str(len(order))).replace('__NCASE__', str(len(by_sample)))
         .replace('__ASSEMBLY__', ASSEMBLY).replace('__NOW__', now)]

for sample in sorted(by_sample):
    keys = by_sample[sample]
    n = {}
    for k in keys:
        n[variant[k]['tier']] = n.get(variant[k]['tier'], 0) + 1
    tv = variant[keys[0]]

    headline = '%s %s &mdash; %s, %s' % (
        esc(tv['gene']),
        esc(tv['hgvsp'] or tv['hgvsc'] or f"{tv['chrom']}:{tv['pos']}"),
        CSQ_LABEL.get(tv['csq'], tv['csq']).lower(), esc(tv['origin']))

    H.append(f'<h2 id="{sample}">{sample}</h2>\n')
    H.append('<div class="summary">')
    H.append('<div class="stat"><b>%d</b>unique variants</div>' % len(keys))
    H.append('<div class="stat"><b>%d</b>tier A</div>' % n.get('A', 0))
    H.append('<div class="stat"><b>%d</b>tier B</div>' % n.get('B', 0))
    H.append('<div class="stat"><b>%d</b>tier C</div>' % n.get('C', 0))
    H.append('<div class="stat"><b style="font-size:.95rem">%s</b>leading candidate</div>'
             % headline)
    H.append('</div>\n')

    H.append('<table>\n<thead><tr>')
    H.append('<th data-i="0">Tier</th><th data-i="1">Gene</th><th data-i="2">Variant</th>')
    H.append('<th data-i="3">Consequence</th><th data-i="4">Inheritance &amp; segregation</th>')
    H.append('<th data-i="5">gnomAD</th><th data-i="6">ClinVar</th>')
    H.append('<th data-i="7" class="hide-sm">Talos evidence</th>')
    H.append('</tr></thead>\n')

    for key in keys:
        v = variant[key]
        vid = '-'.join([v['chrom'], v['pos'], v['ref'], v['alt']])

        variant_cell = '<span class="mono">%s</span>' % esc(v['hgvsp'] or v['hgvsc'] or '-')
        variant_cell += ('<br><span class="mono muted">chr%s:%s %s&gt;%s</span>'
                         % (esc(v['chrom']), esc(v['pos']), esc(v['ref']), esc(v['alt'])))

        inh = '<br>'.join(esc(m) for m in v['mois_l']) or '<span class="muted">-</span>'
        inh += ('<br><span class="muted">%s &middot; %s</span>'
                % (esc(v['origin']), esc(v['gt_string'])))

        if v['clinvar'] is not None:
            cv = esc(v['clinvar'])
            if v['stars'] is not None:
                cv += ('<br><span class="muted">%d review star%s</span>'
                       % (v['stars'], '' if v['stars'] == 1 else 's'))
        else:
            cv = '<span class="muted">not in ClinVar</span>'

        ev = []
        if v['cat1']:
            ev.append('<span class="chip">Cat 1 ClinVar</span>')
        if v['cat2']:
            ev.append('<span class="chip">Cat 2 new gene</span>')
        if v['cat3']:
            ev.append('<span class="chip">Cat 3 high impact</span>')
        if v['denovo']:
            ev.append('<span class="chip">Cat 4 de novo</span>')
        if v['pm5']:
            ev.append('<span class="chip">PM5</span>')
        if v['am_class'] is not None:
            ev.append('<span class="chip">AM %s</span>' % esc(v['am_class']))
        if v['warnings']:
            ev.append('<span class="chip">!</span>')

        search = ' '.join([v['gene'], vid, v['csq'], v['hgvsp'] or '',
                           ' '.join(v['mois_l']), v['origin'], v['clinvar'] or '',
                           ' '.join(v['panels'])]).lower()

        H.append('<tbody class="cand" data-tier="%s" data-s="%s">\n' % (v['tier'], esc(search)))
        H.append('<tr class="main">')
        H.append('<td data-v="%s"><span class="tier %s">%s</span></td>'
                 % (v['tier'], v['tier'], v['tier']))
        H.append('<td data-v="%s" class="gene">%s</td>' % (esc(v['gene']), esc(v['gene'])))
        H.append('<td data-v="%s">%s</td>' % (esc(vid), variant_cell))
        H.append('<td data-v="%s">%s</td>'
                 % (esc(v['csq']), esc(CSQ_LABEL.get(v['csq'], v['csq']))))
        H.append('<td data-v="%s">%s</td>' % (esc(';'.join(v['mois_l'])), inh))
        H.append('<td data-v="%s" class="mono">%s</td>'
                 % (pnum(v['af']) if v['af'] is not None else '-1', esc(fmt_af(v['af']))))
        H.append('<td data-v="%s">%s</td>' % (esc(v['clinvar'] or 'zzz'), cv))
        H.append('<td data-v="" class="hide-sm">%s</td>' % (''.join(ev) or '-'))
        H.append('</tr>\n')

        # ---- detail row
        why = ''.join('<li>%s</li>' % esc(w) for w in v['why']) \
            or '<li class="muted">No positive evidence in this file.</li>'
        cav = ''.join('<li>%s</li>' % esc(c) for c in v['caveats'])

        parts = (v['tech'].split('|') + ['', '', '', ''])[:4]
        enst, ensp, biotype, flag = parts

        dl = []
        dl.append('<dt>CADD</dt><dd>' + (pnum(v['cadd']) if v['cadd'] is not None
                                         else '<span class="muted">-</span>') + '</dd>')
        dl.append('<dt>REVEL</dt><dd>' + (pnum(v['revel']) if v['revel'] is not None
                                          else '<span class="muted">-</span>') + '</dd>')
        dl.append('<dt>SIFT</dt><dd>' + esc(dash(v['sift'])) + '</dd>')
        dl.append('<dt>PolyPhen</dt><dd>' + esc(dash(v['polyphen'])) + '</dd>')
        if v['am_class'] is not None:
            am = esc(v['am_class'])
            if v['am_score'] is not None:
                am += ' (%s)' % pnum(v['am_score'])
        else:
            am = '<span class="muted">-</span>'
        dl.append('<dt>AlphaMissense</dt><dd>' + am + '</dd>')

        dl2 = []
        dl2.append('<dt>Transcript</dt><dd class="mono">' + esc(dash(enst)) + '</dd>')
        dl2.append('<dt>Protein</dt><dd class="mono">' + esc(dash(ensp)) + '</dd>')
        dl2.append('<dt>Biotype</dt><dd>' + esc(dash(biotype)) + '</dd>')
        dl2.append('<dt>MANE / exon</dt><dd>' + esc(dash(flag)) + '</dd>')
        dl2.append('<dt>HGVSc</dt><dd class="mono">' + esc(dash(v['hgvsc'])) + '</dd>')
        dl2.append('<dt>Panels</dt><dd>' + (esc('; '.join(v['panels'])) or '-') + '</dd>')
        dl2.append('<dt>First tagged</dt><dd>' + esc(dash(v['tagged'])) + '</dd>')
        dl2.append('<dt>Source rows</dt><dd>' + ', '.join(str(r) for r in v['rows']) + '</dd>')

        gnomad_v = f'https://gnomad.broadinstitute.org/variant/{vid}?dataset=gnomad_r4'
        gnomad_g = f"https://gnomad.broadinstitute.org/gene/{v['gene_id']}?dataset=gnomad_r4"
        clinvar_l = f"https://www.ncbi.nlm.nih.gov/clinvar/?term={v['gene']}%5Bgene%5D"
        ens_l = f"https://www.ensembl.org/Homo_sapiens/Gene/Summary?g={v['gene_id']}"
        panel_l = f"https://panelapp.genomicsengland.co.uk/panels/entities/{v['gene']}"
        omim_l = f"https://www.omim.org/search?search={v['gene']}"

        H.append('<tr class="detail"><td colspan="8">\n<div class="grid">\n')
        H.append(f'<div><h3>Why prioritised</h3><ul class="why">{why}</ul>')
        if cav:
            H.append(f'<h3>Caveats</h3><ul class="why cav">{cav}</ul>')
        H.append('</div>\n')
        H.append('<div><h3>In silico</h3><dl>' + ''.join(dl) + '</dl></div>\n')
        H.append('<div><h3>Annotation</h3><dl>' + ''.join(dl2) + '</dl></div>\n')
        H.append('<div><h3>External</h3><div class="links">')
        H.append(f'<a href="{gnomad_v}" target="_blank" rel="noopener">gnomAD variant</a>')
        H.append(f'<a href="{gnomad_g}" target="_blank" rel="noopener">gnomAD gene</a>')
        H.append(f'<a href="{clinvar_l}" target="_blank" rel="noopener">ClinVar</a>')
        H.append(f'<a href="{ens_l}" target="_blank" rel="noopener">Ensembl</a>')
        H.append(f'<a href="{panel_l}" target="_blank" rel="noopener">PanelApp</a>')
        H.append(f'<a href="{omim_l}" target="_blank" rel="noopener">OMIM</a>')
        H.append('</div></div>\n')
        H.append('</div>\n</td></tr>\n</tbody>\n')
    H.append('</table>\n')

# --- cleaning appendix ---
H.append('<h2>Appendix &mdash; what was cleaned</h2>\n')
H.append('''<div class="note"><p>The source file mixes encodings for the same facts.
Every change below is mechanical and reversible; nothing was inferred beyond the
rules listed here.</p></div>\n''')
H.append('<ul class="why">\n')
H.append('<li><b>Sample IDs</b> trimmed and upper-cased (<span class="mono">sample_1</span>, <span class="mono">\'SAMPLE_1 \'</span> &rarr; <span class="mono">SAMPLE_1</span>).</li>\n')
H.append('<li><b>Chromosomes</b> stripped of the <span class="mono">chr</span> prefix so <span class="mono">chr6</span> and <span class="mono">6</span> collapse to one variant.</li>\n')
H.append('<li><b>Booleans</b> unified from <span class="mono">TRUE/True/yes/1</span> and <span class="mono">FALSE/False/no/0</span>.</li>\n')
H.append('<li><b>Talos category 4</b> holds a sample ID, not a boolean; it is read as de novo only when it matches that row\'s own sample.</li>\n')
H.append('<li><b>Modes of inheritance</b> mapped to full phrases (<span class="mono">AD</span> and <span class="mono">Autosomal Dominant</span> are the same thing).</li>\n')
H.append('<li><b>Genotypes</b> parsed out of the embedded JSON and used to infer parental origin and compound-heterozygous phase.</li>\n')
H.append('<li><b>Protein changes</b> stripped of accession prefixes and parentheses, and converted to three-letter code (<span class="mono">p.P405S</span> &rarr; <span class="mono">p.Pro405Ser</span>).</li>\n')
H.append('<li><b>HGVSc</b> kept only where it is real HGVS; pseudo-notation such as <span class="mono">135912503G&gt;A</span> was dropped in favour of the genomic coordinate.</li>\n')
H.append('<li><b>gnomAD AF</b> rounded to three significant figures, removing float noise (<span class="mono">2.499999936844688e-06</span> &rarr; <span class="mono">2.5e-06</span>).</li>\n')
H.append('<li><b>ClinVar</b> synonyms merged (<span class="mono">P/LP</span>, <span class="mono">VUS</span>).</li>\n')
H.append('<li><b>Null markers</b> <span class="mono">missing</span>, <span class="mono">.</span> and empty all treated as no data.</li>\n')
H.append('<li><b>Dates</b> converted to ISO (<span class="mono">14/08/2026</span> &rarr; <span class="mono">2026-08-14</span>).</li>\n')
H.append('<li><b>Duplicates</b> merged on sample + position + alleles: %d source rows &rarr; %d unique variants.</li>\n'
         % (n_rows, len(order)))
H.append('</ul>\n')

H.append('<h3>Flags raised while cleaning</h3>\n<ul class="why cav">\n')
for note in QC:
    H.append('<li>%s</li>\n' % esc(note))
H.append('</ul>\n')

FOOT = """<div class="foot">
<p>Generated by <code>tidy_talos.pl / tidy_talos.py</code> from <code>__IN__</code> on __NOW__.
Assembly (__ASSEMBLY__) is inferred from the coordinates, not declared in the source file &mdash;
confirm before using the external links.
Talos category labels follow the public Talos documentation; check them against your Talos version.</p>
<p>Synthetic workshop data. No patient data. Not a clinical report.</p>
</div>
</div>
<script>
(function(){
  document.querySelectorAll('tbody.cand>tr.main').forEach(function(r){
    r.addEventListener('click',function(){ r.parentNode.classList.toggle('open'); });
  });
  document.getElementById('expand').onclick=function(){
    document.querySelectorAll('tbody.cand').forEach(function(t){t.classList.add('open');});
  };
  document.getElementById('collapse').onclick=function(){
    document.querySelectorAll('tbody.cand').forEach(function(t){t.classList.remove('open');});
  };
  document.getElementById('theme').onclick=function(){
    var r=document.documentElement;
    var dark=getComputedStyle(document.body).backgroundColor==='rgb(21, 24, 28)';
    r.setAttribute('data-theme', dark?'light':'dark');
  };
  function apply(){
    var q=document.getElementById('q').value.toLowerCase().trim();
    var tiers=Array.prototype.filter.call(document.querySelectorAll('.tf'),function(c){return c.checked;})
      .map(function(c){return c.value;});
    document.querySelectorAll('tbody.cand').forEach(function(t){
      var ok=tiers.indexOf(t.dataset.tier)>-1 && (!q || t.dataset.s.indexOf(q)>-1);
      t.style.display = ok ? '' : 'none';
    });
  }
  document.getElementById('q').addEventListener('input',apply);
  document.querySelectorAll('.tf').forEach(function(c){c.addEventListener('change',apply);});

  document.querySelectorAll('th[data-i]').forEach(function(th){
    th.addEventListener('click',function(){
      var table=th.closest('table'), i=+th.dataset.i;
      var dir=th.dataset.dir==='asc'?-1:1;
      table.querySelectorAll('th[data-i]').forEach(function(o){delete o.dataset.dir;});
      th.dataset.dir=dir===1?'asc':'desc';
      var bodies=Array.prototype.slice.call(table.querySelectorAll('tbody.cand'));
      bodies.sort(function(a,b){
        var x=a.querySelector('tr.main').children[i].dataset.v||'';
        var y=b.querySelector('tr.main').children[i].dataset.v||'';
        var nx=parseFloat(x), ny=parseFloat(y);
        if(!isNaN(nx)&&!isNaN(ny)) return (nx-ny)*dir;
        return x.localeCompare(y)*dir;
      });
      bodies.forEach(function(t){table.appendChild(t);});
    });
  });
})();
</script>
</body>
</html>
"""
H.append(FOOT.replace('__IN__', IN).replace('__NOW__', now).replace('__ASSEMBLY__', ASSEMBLY))

with open(os.path.join(OUTDIR, 'talos_case_report.html'), 'w',
          encoding='utf-8', newline='\n') as html:
    html.write(''.join(H))

print(f'read {n_rows} rows -> {len(order)} unique variants across {len(by_sample)} cases')
print(f'wrote {OUTDIR}/talos_candidates_tidy.tsv')
print(f'wrote {OUTDIR}/talos_case_report.html')
print(f'wrote {OUTDIR}/talos_cleaning_log.txt ({len(QC)} notes)')
