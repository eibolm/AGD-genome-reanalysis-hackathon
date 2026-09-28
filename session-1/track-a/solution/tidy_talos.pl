#!/usr/bin/env perl
# Session 1 / Track A -- turn messy_talos_candidates.tsv into a clinician-readable summary.
#
#   perl tidy_talos.pl [input.tsv] [output_dir]
#
# Writes:
#   talos_candidates_tidy.tsv   one row per unique variant, normalised columns
#   talos_case_report.html      per-case review report
#   talos_cleaning_log.txt      every change made to the source data

use strict;
use warnings;

my $IN     = shift || 'session-1/track-a/messy_talos_candidates.tsv';
my $OUTDIR = shift || 'session-1/track-a/solution';
mkdir $OUTDIR unless -d $OUTDIR;

# Coordinates match GRCh38 for every row checked (e.g. RNU4-2 at 12:120291834).
# The source file carries no assembly column, so this is inferred, not declared.
my $ASSEMBLY = 'GRCh38';

my @QC;    # data-quality notes raised while cleaning
sub qc { push @QC, join('', @_) }

# ---------------------------------------------------------------- helpers ---
sub trim { my $s = shift; $s = '' unless defined $s; $s =~ s/^\s+|\s+$//g; $s }

sub nullish {
    my $s = lc trim(shift);
    return ($s eq '' || $s eq 'missing' || $s eq '.' || $s eq 'na' || $s eq 'nan') ? 1 : 0;
}
sub val { my $s = shift; nullish($s) ? undef : trim($s) }

sub to_bool {
    my $s = lc trim(shift);
    return 1 if $s =~ /^(true|yes|y|1)$/;
    return 0;
}

sub num {
    my $v = val(shift);
    return undef unless defined $v;
    return undef unless $v =~ /^[-+]?[0-9.]+([eE][-+]?\d+)?$/;
    return $v + 0;
}

# gnomAD AFs arrive with float noise (2.499999936844688e-06); 3 sig figs is plenty.
sub fmt_af {
    my $af = shift;
    return 'not reported' unless defined $af;
    return 'absent (0)'   if $af == 0;
    return sprintf('%.3g', $af);
}

sub iso_date {
    my $d = val(shift);
    return undef unless defined $d;
    return $d if $d =~ /^\d{4}-\d{2}-\d{2}$/;
    if ($d =~ m{^(\d{1,2})/(\d{1,2})/(\d{4})$}) {
        return sprintf('%04d-%02d-%02d', $3, $2, $1);   # DD/MM/YYYY
    }
    return $d;
}

sub norm_chrom {
    my $c = trim(shift);
    $c =~ s/^chr//i;
    $c = uc $c if $c =~ /^[xym]/i;
    $c = 'MT'  if $c eq 'M';
    return $c;
}

# The genotypes column is a JSON object embedded in a TSV, so its quotes are doubled.
sub parse_gts {
    my $raw = trim(shift);
    $raw =~ s/^"//;
    $raw =~ s/"$//;
    $raw =~ s/""/"/g;
    my %g;
    while ($raw =~ /"([^"]+)"\s*:\s*"([^"]*)"/g) { $g{lc $1} = $2 }
    return \%g;
}

my %CSQ_ALIAS = (
    missense   => 'missense_variant',
    non_coding => 'non_coding_transcript_exon_variant',
);
my %CSQ_LABEL = (
    frameshift_variant                 => 'Frameshift',
    splice_donor_variant               => 'Splice donor',
    splice_acceptor_variant            => 'Splice acceptor',
    stop_gained                        => 'Stop gained (nonsense)',
    missense_variant                   => 'Missense',
    non_coding_transcript_exon_variant => 'Non-coding transcript',
);
my %IS_LOF = map { $_ => 1 }
    qw(frameshift_variant splice_donor_variant splice_acceptor_variant stop_gained);

sub norm_moi {
    my $m = trim(shift);
    return undef if $m eq '';
    my $l = lc $m;
    return 'Autosomal dominant'                 if $l eq 'ad' or $l eq 'autosomal dominant';
    return 'Autosomal recessive (homozygous)'   if $l =~ /^ar\s*\(hom/;
    return 'Autosomal recessive (compound het)' if $l =~ /^ar\s*\(comp/;
    return 'X-linked recessive'                 if $l =~ /x-?linked\s+recessive/;
    return $m;
}

sub norm_clinvar {
    my $c = val(shift);
    return undef unless defined $c;
    my $l = lc $c;
    return 'Pathogenic / Likely pathogenic' if $l eq 'p/lp' or $l eq 'pathogenic/likely pathogenic';
    return 'Uncertain significance (VUS)'   if $l eq 'vus' or $l eq 'uncertain significance';
    return 'Benign / Likely benign'         if $l eq 'b/lb' or $l eq 'benign/likely benign';
    return $c;
}

my %AA = (A=>'Ala',R=>'Arg',N=>'Asn',D=>'Asp',C=>'Cys',Q=>'Gln',E=>'Glu',G=>'Gly',
          H=>'His',I=>'Ile',L=>'Leu',K=>'Lys',M=>'Met',F=>'Phe',P=>'Pro',S=>'Ser',
          T=>'Thr',W=>'Trp',Y=>'Tyr',V=>'Val',X=>'Ter');

sub norm_hgvsp {
    my $p = val(shift);
    return undef unless defined $p;
    $p =~ s/^[^:]*:// if $p =~ /:p\./;        # drop ENSP accession prefix
    $p =~ s/^p\.\((.+)\)$/p.$1/;              # drop the "predicted" parentheses
    if ($p =~ /^p\.([A-Z])(\d+)([A-Z*])$/) {  # 1-letter -> 3-letter
        my ($a, $n, $b) = ($1, $2, $3);
        my $from = $AA{$a};
        my $to   = $b eq '*' ? 'Ter' : $AA{$b};
        $p = "p.$from$n$to" if $from and $to;
    }
    return $p;
}

sub norm_hgvsc {
    my $c = val(shift);
    return undef unless defined $c;
    $c =~ s/^[^:]*:// if $c =~ /:c\./;
    return $c if $c =~ /^c\./;
    return undef;    # "135912503G>A" looks like HGVS but is not; drop it
}

sub fmt_pred {
    my $s = val(shift);
    return undef unless defined $s;
    if ($s =~ /^([a-z_]+)\(([^)]*)\)$/i) {
        my ($t, $v) = ($1, $2);
        $t =~ s/_/ /g;
        return ucfirst($t) . " ($v)";
    }
    return $s;
}

# Identical variant reported more than once: OR the evidence flags, union the
# warnings and modes of inheritance, keep the first non-empty annotation.
sub merge_rec {
    my ($v, $r) = @_;
    push @{ $v->{rows} }, $r->{row};
    for my $f (qw(cat1 cat2 cat3 denovo pm5)) { $v->{$f} ||= $r->{$f} }
    for my $f (qw(am_class am_score hgvsc hgvsp af clinvar stars cadd revel
                  sift polyphen tagged tech gene gene_id)) {
        $v->{$f} = $r->{$f} if !defined $v->{$f} and defined $r->{$f};
    }
    $v->{panels} = $r->{panels} if @{ $r->{panels} } > @{ $v->{panels} };
}

# ------------------------------------------------------------------ read ----
open my $fh, '<', $IN or die "cannot open $IN: $!";
# The source file is CRLF; chomp alone leaves a \r glued to the last column name.
my $hdr = <$fh>;
$hdr =~ s/\r?\n\z//;
my @cols = split /\t/, $hdr;
my %ix;
$ix{ $cols[$_] } = $_ for 0 .. $#cols;

my (%variant, @order);
my $n_rows = 0;

while (my $line = <$fh>) {
    $line =~ s/\r?\n\z//;
    next unless $line =~ /\S/;
    $n_rows++;
    my @f = split /\t/, $line, -1;
    my $get = sub {
        my $c = shift;
        return (defined $ix{$c} && defined $f[ $ix{$c} ]) ? $f[ $ix{$c} ] : '';
    };

    my $raw_sample = $get->('sample_id');
    my $sample     = uc trim($raw_sample);
    qc("row $n_rows: sample_id '$raw_sample' normalised to '$sample'")
        if trim($raw_sample) ne $sample or $raw_sample ne trim($raw_sample);

    my $raw_chrom = $get->('chromosome');
    my $chrom     = norm_chrom($raw_chrom);
    qc("row $n_rows: chromosome '$raw_chrom' normalised to '$chrom'")
        if trim($raw_chrom) ne $chrom;

    my ($pos, $ref, $alt) = (trim($get->('position')), trim($get->('REF')), trim($get->('ALT')));
    my $key = join '|', $sample, $chrom, $pos, $ref, $alt;

    my $raw_csq = lc trim($get->('consequence'));
    my $csq     = $CSQ_ALIAS{$raw_csq} || $raw_csq;
    qc("row $n_rows: consequence '$raw_csq' standardised to '$csq'") if $csq ne $raw_csq;

    # Talos category 4 (de novo) holds the sample ID it fired for, not a boolean,
    # so compare it with this row's sample rather than casting it.
    my $raw_c4 = uc trim($get->('Talos_category_4'));
    my $denovo = ($raw_c4 ne '' && $raw_c4 eq $sample) ? 1 : 0;

    my $raw_hgvsc = val($get->('MANE_HGVSc'));
    my $hgvsc     = norm_hgvsc($get->('MANE_HGVSc'));
    qc("row $n_rows: MANE_HGVSc '$raw_hgvsc' is not HGVS notation and was dropped")
        if defined $raw_hgvsc and not defined $hgvsc;

    my $raw_date = val($get->('first_tagged'));
    my $date     = iso_date($get->('first_tagged'));
    qc("row $n_rows: first_tagged '$raw_date' reformatted to '$date'")
        if defined $raw_date and defined $date and $raw_date ne $date;

    my $rec = {
        row      => $n_rows,
        sample   => $sample,
        gene     => trim($get->('gene_symbol')),
        gene_id  => trim($get->('gene_id')),
        chrom    => $chrom,
        pos      => $pos,
        ref      => $ref,
        alt      => $alt,
        cat1     => to_bool($get->('Talos_category_1')),
        cat2     => to_bool($get->('Talos_category_2')),
        cat3     => to_bool($get->('Talos_category_3')),
        denovo   => $denovo,
        pm5      => to_bool($get->('PM5')),
        am_class => val($get->('AlphaMissense_class')),
        am_score => num($get->('AlphaMissense_score')),
        moi      => norm_moi($get->('inheritance_reason')),
        gts      => parse_gts($get->('genotypes')),
        csq      => $csq,
        hgvsc    => $hgvsc,
        hgvsp    => norm_hgvsp($get->('MANE_HGVSp')),
        af       => num($get->('gnomAD_AF')),
        clinvar  => norm_clinvar($get->('ClinVar')),
        stars    => num($get->('ClinVar_stars')),
        cadd     => num($get->('CADD')),
        revel    => num($get->('REVEL')),
        sift     => fmt_pred($get->('SIFT')),
        polyphen => fmt_pred($get->('PolyPhen')),
        panels   => [ grep { $_ ne '' } map { trim($_) } split /;/, trim($get->('panels')) ],
        tagged   => $date,
        warning  => val($get->('warnings')),
        tech     => trim($get->('extra_technical_field')),
    };

    if (!exists $variant{$key}) {
        $variant{$key} = { %$rec, rows => [ $n_rows ], mois => {}, warnings => {} };
        push @order, $key;
    } else {
        merge_rec($variant{$key}, $rec);
    }
    my $v = $variant{$key};
    $v->{mois}{ $rec->{moi} }        = 1 if defined $rec->{moi};
    $v->{warnings}{ $rec->{warning} } = 1 if defined $rec->{warning};
}
close $fh;

for my $key (@order) {
    my $v = $variant{$key};
    next unless @{ $v->{rows} } > 1;
    qc("$key: source rows ", join(', ', @{ $v->{rows} }), " describe the same variant and were merged");
    my @m = sort keys %{ $v->{mois} };
    qc("$key: merged rows disagree on mode of inheritance (", join(' vs ', @m), ")") if @m > 1;
}

# ------------------------------------------------- segregation & phasing ----
for my $key (@order) {
    my $v = $variant{$key};
    my $g = $v->{gts};
    my $p = uc($g->{proband} || '');
    my $m = uc($g->{mother}  || '');
    my $d = uc($g->{father}  || '');
    $v->{gt_string} = "proband $p / mother $m / father $d";

    my $carrier = sub { my $x = shift; ($x eq 'HET' or $x eq 'HOM' or $x eq 'HEMI') ? 1 : 0 };
    if    ($p eq 'HOM')                                 { $v->{origin} = 'biparental' }
    elsif ($p eq 'HEMI' and $m eq 'HET')                { $v->{origin} = 'maternal' }
    elsif ($p eq 'HET' and $m eq 'WT'  and $d eq 'WT')  { $v->{origin} = 'de novo' }
    elsif ($p eq 'HET' and $carrier->($m) and $d eq 'WT') { $v->{origin} = 'maternal' }
    elsif ($p eq 'HET' and $carrier->($d) and $m eq 'WT') { $v->{origin} = 'paternal' }
    else                                                { $v->{origin} = 'unresolved' }

    if ($v->{denovo} and $v->{origin} ne 'de novo') {
        qc("$key: Talos category 4 (de novo) is set, but trio genotypes read $v->{gt_string}");
    }
}

# Pair compound heterozygotes within a sample+gene and check they are in trans.
my %by_gene;
for my $key (@order) {
    push @{ $by_gene{ $variant{$key}{sample} . '|' . $variant{$key}{gene} } }, $key;
}
for my $grp (values %by_gene) {
    next unless @$grp > 1;
    for my $a (@$grp) {
        my @partners;
        for my $b (@$grp) {
            next if $a eq $b;
            my $oa = $variant{$a}{origin};
            my $ob = $variant{$b}{origin};
            next unless $oa =~ /^(maternal|paternal|de novo)$/
                    and $ob =~ /^(maternal|paternal|de novo)$/;
            push @partners, { key => $b, trans => ($oa ne $ob ? 1 : 0) };
        }
        $variant{$a}{partners} = \@partners;
    }
}

# ----------------------------------------------------------- tier & why -----
for my $key (@order) {
    my $v = $variant{$key};
    my (@why, @caveats);

    my $plp   = (defined $v->{clinvar} and $v->{clinvar} =~ /^Pathogenic/) ? 1 : 0;
    my $lof   = $IS_LOF{ $v->{csq} } ? 1 : 0;
    my $hom   = ($v->{origin} eq 'biparental') ? 1 : 0;
    my $hemi  = (uc($v->{gts}{proband} || '') eq 'HEMI') ? 1 : 0;
    my $dn    = ($v->{origin} eq 'de novo') ? 1 : 0;
    my @trans = grep { $_->{trans} } @{ $v->{partners} || [] };

    if ($plp) {
        my $s = 'ClinVar pathogenic / likely pathogenic';
        $s .= sprintf(' (%d review star%s)', $v->{stars}, $v->{stars} == 1 ? '' : 's')
            if defined $v->{stars};
        push @why, $s;
    }
    push @why, 'De novo in proband (both parents wild-type)' if $dn;
    push @why, 'Predicted loss of function: ' . lc($CSQ_LABEL{ $v->{csq} } || $v->{csq}) if $lof;
    push @why, 'Homozygous in proband, both parents heterozygous' if $hom;
    push @why, 'Hemizygous in proband, maternally inherited' if $hemi;
    if (@trans) {
        my $pv = $variant{ $trans[0]{key} };
        push @why, sprintf('Compound heterozygous in trans with %s:%s %s>%s (%s vs %s)',
            $pv->{chrom}, $pv->{pos}, $pv->{ref}, $pv->{alt}, $v->{origin}, $pv->{origin});
        $v->{comphet} = sprintf('%s:%s %s>%s', $pv->{chrom}, $pv->{pos}, $pv->{ref}, $pv->{alt});
    }
    push @why, sprintf('AlphaMissense %s (%.2f)', $v->{am_class}, $v->{am_score})
        if defined $v->{am_class} and $v->{am_class} eq 'likely_pathogenic';
    push @why, 'ACMG PM5 flagged by Talos' if $v->{pm5};
    push @why, 'Absent from gnomAD' if defined $v->{af} and $v->{af} == 0;
    push @why, sprintf('Ultra-rare in gnomAD (%s)', fmt_af($v->{af}))
        if defined $v->{af} and $v->{af} > 0;
    push @why, sprintf('CADD %.1f', $v->{cadd}) if defined $v->{cadd} and $v->{cadd} >= 25;

    push @caveats, sprintf('AlphaMissense %s (%.2f)', $v->{am_class}, $v->{am_score})
        if defined $v->{am_class} and $v->{am_class} =~ /benign|ambiguous/;
    push @caveats, 'Not present in ClinVar' unless defined $v->{clinvar};
    push @caveats, 'ClinVar: uncertain significance'
        if defined $v->{clinvar} and $v->{clinvar} =~ /Uncertain/;
    push @caveats, 'gnomAD frequency not reported' unless defined $v->{af};
    push @caveats, "Talos QC warning: $_" for sort keys %{ $v->{warnings} };

    my @mois = sort keys %{ $v->{mois} };
    push @caveats, 'Source rows disagree on mode of inheritance: ' . join(' vs ', @mois)
        if @mois > 1;
    push @caveats, 'Reported in ' . scalar(@{ $v->{rows} }) . ' source rows (merged)'
        if @{ $v->{rows} } > 1;

    # Talos category 1 is the ClinVar-driven category; firing it with no ClinVar
    # record is a contradiction in the source data, not a finding.
    if ($v->{cat1} and !defined $v->{clinvar}) {
        push @caveats, 'Talos category 1 set but no ClinVar record in this file';
        qc("$key: Talos_category_1 is TRUE but the ClinVar column is empty/missing");
    }

    my $benign = (defined $v->{am_class} and $v->{am_class} eq 'likely_benign') ? 1 : 0;
    my $tier;
    if ($plp and ($lof or $dn or $hom or $hemi or @trans)) {
        $tier = 'A';
    } elsif ($plp
          or ($dn and $lof)
          or (@trans and defined $v->{am_class} and $v->{am_class} eq 'likely_pathogenic')) {
        $tier = 'B';
    } else {
        $tier = 'C';
    }
    $tier = 'C' if $benign and !$plp;

    $v->{why}     = \@why;
    $v->{caveats} = \@caveats;
    $v->{tier}    = $tier;
    $v->{mois_l}  = \@mois;
}

my %TIER_RANK = (A => 0, B => 1, C => 2);
my @sorted = sort {
       $variant{$a}{sample}            cmp $variant{$b}{sample}
    || $TIER_RANK{ $variant{$a}{tier} } <=> $TIER_RANK{ $variant{$b}{tier} }
    || ($variant{$b}{cadd} || 0)        <=> ($variant{$a}{cadd} || 0)
    || $variant{$a}{gene}               cmp $variant{$b}{gene}
} @order;

# ------------------------------------------------------------- output ------
sub esc {
    my $s = shift;
    $s = '' unless defined $s;
    $s =~ s/&/&amp;/g;
    $s =~ s/</&lt;/g;
    $s =~ s/>/&gt;/g;
    $s =~ s/"/&quot;/g;
    return $s;
}
sub dash { my $s = shift; (defined $s and $s ne '') ? $s : '-' }

my @t   = localtime;
my $now = sprintf('%04d-%02d-%02d %02d:%02d', $t[5] + 1900, $t[4] + 1, $t[3], $t[2], $t[1]);

# --- tidy TSV ---------------------------------------------------------------
my @OUT_COLS = qw(
    sample_id tier gene_symbol gene_id assembly chrom pos ref alt variant_id
    hgvs_c hgvs_p consequence consequence_label loss_of_function
    mode_of_inheritance proband_gt mother_gt father_gt inferred_origin comphet_partner
    gnomad_af clinvar clinvar_stars cadd revel sift polyphen
    alphamissense_class alphamissense_score
    talos_cat1 talos_cat2 talos_cat3 talos_cat4_de_novo talos_pm5
    panels first_tagged talos_warnings why_prioritised caveats source_rows
);

open my $tsv, '>', "$OUTDIR/talos_candidates_tidy.tsv" or die $!;
print $tsv join("\t", @OUT_COLS), "\n";
for my $key (@sorted) {
    my $v = $variant{$key};
    my @r = (
        $v->{sample}, $v->{tier}, $v->{gene}, $v->{gene_id}, $ASSEMBLY,
        $v->{chrom}, $v->{pos}, $v->{ref}, $v->{alt},
        join('-', $v->{chrom}, $v->{pos}, $v->{ref}, $v->{alt}),
        dash($v->{hgvsc}), dash($v->{hgvsp}), $v->{csq},
        $CSQ_LABEL{ $v->{csq} } || $v->{csq},
        ($IS_LOF{ $v->{csq} } ? 'yes' : 'no'),
        join('; ', @{ $v->{mois_l} }),
        uc($v->{gts}{proband} || ''), uc($v->{gts}{mother} || ''), uc($v->{gts}{father} || ''),
        $v->{origin}, dash($v->{comphet}),
        (defined $v->{af} ? sprintf('%.3g', $v->{af}) : ''),
        dash($v->{clinvar}), (defined $v->{stars} ? $v->{stars} : ''),
        (defined $v->{cadd} ? $v->{cadd} : ''), (defined $v->{revel} ? $v->{revel} : ''),
        dash($v->{sift}), dash($v->{polyphen}),
        dash($v->{am_class}), (defined $v->{am_score} ? $v->{am_score} : ''),
        ($v->{cat1} ? 'yes' : 'no'), ($v->{cat2} ? 'yes' : 'no'), ($v->{cat3} ? 'yes' : 'no'),
        ($v->{denovo} ? 'yes' : 'no'), ($v->{pm5} ? 'yes' : 'no'),
        join('; ', @{ $v->{panels} }), dash($v->{tagged}),
        join('; ', sort keys %{ $v->{warnings} }),
        join(' | ', @{ $v->{why} }), join(' | ', @{ $v->{caveats} }),
        join(',', @{ $v->{rows} }),
    );
    print $tsv join("\t", map { defined $_ ? $_ : '' } @r), "\n";
}
close $tsv;

# --- cleaning log -----------------------------------------------------------
open my $log, '>', "$OUTDIR/talos_cleaning_log.txt" or die $!;
print $log "Talos candidate table -- cleaning log\n";
print $log "source: $IN\ngenerated: $now\n";
printf $log "source rows: %d -> unique variants: %d\n\n", $n_rows, scalar(@order);
print $log "$_\n" for @QC;
close $log;

# --- HTML report ------------------------------------------------------------
my %by_sample;
push @{ $by_sample{ $variant{$_}{sample} } }, $_ for @sorted;

my @H;
push @H, <<"HEAD";
<!DOCTYPE html>
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
\@media (prefers-color-scheme: dark){
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
\@media (max-width:720px){
  .wrap{padding:16px}
  table{font-size:.8rem}
  th,td{padding:6px 5px}
  .hide-sm{display:none}
}
\@media print{
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
<p class="sub">Source: <span class="mono">$IN</span> &middot; $n_rows source rows condensed to
@{[ scalar @order ]} unique variants across @{[ scalar keys %by_sample ]} cases &middot;
coordinates interpreted as $ASSEMBLY &middot; generated $now</p>

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
HEAD

for my $sample (sort keys %by_sample) {
    my @keys = @{ $by_sample{$sample} };
    my %n;
    $n{ $variant{$_}{tier} }++ for @keys;
    my ($top) = @keys;
    my $tv = $variant{$top};

    my $headline = sprintf('%s %s %s &mdash; %s, %s',
        esc($tv->{gene}),
        esc($tv->{hgvsp} || $tv->{hgvsc} || "$tv->{chrom}:$tv->{pos}"),
        '', lc($CSQ_LABEL{ $tv->{csq} } || $tv->{csq}), esc($tv->{origin}));
    $headline =~ s/\s+&mdash;/ &mdash;/;

    push @H, qq{<h2 id="$sample">$sample</h2>\n};
    push @H, qq{<div class="summary">};
    push @H, sprintf('<div class="stat"><b>%d</b>unique variants</div>', scalar @keys);
    push @H, sprintf('<div class="stat"><b>%d</b>tier A</div>', $n{A} || 0);
    push @H, sprintf('<div class="stat"><b>%d</b>tier B</div>', $n{B} || 0);
    push @H, sprintf('<div class="stat"><b>%d</b>tier C</div>', $n{C} || 0);
    push @H, sprintf('<div class="stat"><b style="font-size:.95rem">%s</b>leading candidate</div>',
        $headline);
    push @H, qq{</div>\n};

    push @H, qq{<table>\n<thead><tr>};
    push @H, '<th data-i="0">Tier</th><th data-i="1">Gene</th><th data-i="2">Variant</th>';
    push @H, '<th data-i="3">Consequence</th><th data-i="4">Inheritance &amp; segregation</th>';
    push @H, '<th data-i="5">gnomAD</th><th data-i="6">ClinVar</th>';
    push @H, '<th data-i="7" class="hide-sm">Talos evidence</th>';
    push @H, "</tr></thead>\n";

    for my $key (@keys) {
        my $v   = $variant{$key};
        my $vid = join('-', $v->{chrom}, $v->{pos}, $v->{ref}, $v->{alt});

        my $variant_cell = sprintf('<span class="mono">%s</span>', esc($v->{hgvsp} || $v->{hgvsc} || '-'));
        $variant_cell .= sprintf('<br><span class="mono muted">chr%s:%s %s&gt;%s</span>',
            esc($v->{chrom}), esc($v->{pos}), esc($v->{ref}), esc($v->{alt}));

        my $inh = join('<br>', map { esc($_) } @{ $v->{mois_l} }) || '<span class="muted">-</span>';
        $inh .= sprintf('<br><span class="muted">%s &middot; %s</span>',
            esc($v->{origin}), esc($v->{gt_string}));

        my $cv = defined $v->{clinvar}
            ? esc($v->{clinvar}) . (defined $v->{stars}
                ? sprintf('<br><span class="muted">%d review star%s</span>',
                    $v->{stars}, $v->{stars} == 1 ? '' : 's')
                : '')
            : '<span class="muted">not in ClinVar</span>';

        my @ev;
        push @ev, '<span class="chip">Cat 1 ClinVar</span>'   if $v->{cat1};
        push @ev, '<span class="chip">Cat 2 new gene</span>'  if $v->{cat2};
        push @ev, '<span class="chip">Cat 3 high impact</span>' if $v->{cat3};
        push @ev, '<span class="chip">Cat 4 de novo</span>'   if $v->{denovo};
        push @ev, '<span class="chip">PM5</span>'             if $v->{pm5};
        push @ev, sprintf('<span class="chip">AM %s</span>', esc($v->{am_class}))
            if defined $v->{am_class};
        push @ev, '<span class="chip">!</span>' if %{ $v->{warnings} };

        my $search = lc join ' ', $v->{gene}, $vid, $v->{csq}, ($v->{hgvsp} || ''),
            join(' ', @{ $v->{mois_l} }), $v->{origin}, ($v->{clinvar} || ''),
            join(' ', @{ $v->{panels} });

        push @H, sprintf(qq{<tbody class="cand" data-tier="%s" data-s="%s">\n}, $v->{tier}, esc($search));
        push @H, '<tr class="main">';
        push @H, sprintf('<td data-v="%s"><span class="tier %s">%s</span></td>',
            $v->{tier}, $v->{tier}, $v->{tier});
        push @H, sprintf('<td data-v="%s" class="gene">%s</td>', esc($v->{gene}), esc($v->{gene}));
        push @H, sprintf('<td data-v="%s">%s</td>', esc($vid), $variant_cell);
        push @H, sprintf('<td data-v="%s">%s</td>', esc($v->{csq}),
            esc($CSQ_LABEL{ $v->{csq} } || $v->{csq}));
        push @H, sprintf('<td data-v="%s">%s</td>', esc(join ';', @{ $v->{mois_l} }), $inh);
        push @H, sprintf('<td data-v="%s" class="mono">%s</td>',
            (defined $v->{af} ? $v->{af} : -1), esc(fmt_af($v->{af})));
        push @H, sprintf('<td data-v="%s">%s</td>', esc($v->{clinvar} || 'zzz'), $cv);
        push @H, sprintf('<td data-v="" class="hide-sm">%s</td>', join('', @ev) || '-');
        push @H, "</tr>\n";

        # ---- detail row
        my $why = join('', map { '<li>' . esc($_) . '</li>' } @{ $v->{why} })
            || '<li class="muted">No positive evidence in this file.</li>';
        my $cav = join('', map { '<li>' . esc($_) . '</li>' } @{ $v->{caveats} });

        my ($enst, $ensp, $biotype, $flag) = split /\|/, $v->{tech};
        $_ = defined $_ ? $_ : '' for ($enst, $ensp, $biotype, $flag);

        my @dl;
        push @dl, '<dt>CADD</dt><dd>'     . (defined $v->{cadd}  ? $v->{cadd}  : '<span class="muted">-</span>') . '</dd>';
        push @dl, '<dt>REVEL</dt><dd>'    . (defined $v->{revel} ? $v->{revel} : '<span class="muted">-</span>') . '</dd>';
        push @dl, '<dt>SIFT</dt><dd>'     . esc(dash($v->{sift}))     . '</dd>';
        push @dl, '<dt>PolyPhen</dt><dd>' . esc(dash($v->{polyphen})) . '</dd>';
        push @dl, '<dt>AlphaMissense</dt><dd>'
            . (defined $v->{am_class}
                ? esc($v->{am_class}) . (defined $v->{am_score} ? " ($v->{am_score})" : '')
                : '<span class="muted">-</span>') . '</dd>';

        my @dl2;
        push @dl2, '<dt>Transcript</dt><dd class="mono">' . esc(dash($enst)) . '</dd>';
        push @dl2, '<dt>Protein</dt><dd class="mono">'    . esc(dash($ensp)) . '</dd>';
        push @dl2, '<dt>Biotype</dt><dd>'                 . esc(dash($biotype)) . '</dd>';
        push @dl2, '<dt>MANE / exon</dt><dd>'             . esc(dash($flag)) . '</dd>';
        push @dl2, '<dt>HGVSc</dt><dd class="mono">'      . esc(dash($v->{hgvsc})) . '</dd>';
        push @dl2, '<dt>Panels</dt><dd>' . (esc(join('; ', @{ $v->{panels} })) || '-') . '</dd>';
        push @dl2, '<dt>First tagged</dt><dd>' . esc(dash($v->{tagged})) . '</dd>';
        push @dl2, '<dt>Source rows</dt><dd>' . join(', ', @{ $v->{rows} }) . '</dd>';

        my $gnomad_v = "https://gnomad.broadinstitute.org/variant/$vid?dataset=gnomad_r4";
        my $gnomad_g = "https://gnomad.broadinstitute.org/gene/$v->{gene_id}?dataset=gnomad_r4";
        my $clinvar_l = 'https://www.ncbi.nlm.nih.gov/clinvar/?term=' . $v->{gene} . '%5Bgene%5D';
        my $ens_l    = "https://www.ensembl.org/Homo_sapiens/Gene/Summary?g=$v->{gene_id}";
        my $panel_l  = "https://panelapp.genomicsengland.co.uk/panels/entities/$v->{gene}";
        my $omim_l   = "https://www.omim.org/search?search=$v->{gene}";

        push @H, qq{<tr class="detail"><td colspan="8">\n<div class="grid">\n};
        push @H, qq{<div><h3>Why prioritised</h3><ul class="why">$why</ul>};
        push @H, qq{<h3>Caveats</h3><ul class="why cav">$cav</ul>} if $cav;
        push @H, qq{</div>\n};
        push @H, '<div><h3>In silico</h3><dl>' . join('', @dl) . '</dl></div>' . "\n";
        push @H, '<div><h3>Annotation</h3><dl>' . join('', @dl2) . '</dl></div>' . "\n";
        push @H, qq{<div><h3>External</h3><div class="links">};
        push @H, qq{<a href="$gnomad_v" target="_blank" rel="noopener">gnomAD variant</a>};
        push @H, qq{<a href="$gnomad_g" target="_blank" rel="noopener">gnomAD gene</a>};
        push @H, qq{<a href="$clinvar_l" target="_blank" rel="noopener">ClinVar</a>};
        push @H, qq{<a href="$ens_l" target="_blank" rel="noopener">Ensembl</a>};
        push @H, qq{<a href="$panel_l" target="_blank" rel="noopener">PanelApp</a>};
        push @H, qq{<a href="$omim_l" target="_blank" rel="noopener">OMIM</a>};
        push @H, qq{</div></div>\n};
        push @H, qq{</div>\n</td></tr>\n</tbody>\n};
    }
    push @H, "</table>\n";
}

# --- cleaning appendix ---
push @H, qq{<h2>Appendix &mdash; what was cleaned</h2>\n};
push @H, qq{<div class="note"><p>The source file mixes encodings for the same facts.
Every change below is mechanical and reversible; nothing was inferred beyond the
rules listed here.</p></div>\n};
push @H, "<ul class=\"why\">\n";
push @H, "<li><b>Sample IDs</b> trimmed and upper-cased (<span class=\"mono\">sample_1</span>, <span class=\"mono\">'SAMPLE_1 '</span> &rarr; <span class=\"mono\">SAMPLE_1</span>).</li>\n";
push @H, "<li><b>Chromosomes</b> stripped of the <span class=\"mono\">chr</span> prefix so <span class=\"mono\">chr6</span> and <span class=\"mono\">6</span> collapse to one variant.</li>\n";
push @H, "<li><b>Booleans</b> unified from <span class=\"mono\">TRUE/True/yes/1</span> and <span class=\"mono\">FALSE/False/no/0</span>.</li>\n";
push @H, "<li><b>Talos category 4</b> holds a sample ID, not a boolean; it is read as de novo only when it matches that row's own sample.</li>\n";
push @H, "<li><b>Modes of inheritance</b> mapped to full phrases (<span class=\"mono\">AD</span> and <span class=\"mono\">Autosomal Dominant</span> are the same thing).</li>\n";
push @H, "<li><b>Genotypes</b> parsed out of the embedded JSON and used to infer parental origin and compound-heterozygous phase.</li>\n";
push @H, "<li><b>Protein changes</b> stripped of accession prefixes and parentheses, and converted to three-letter code (<span class=\"mono\">p.P405S</span> &rarr; <span class=\"mono\">p.Pro405Ser</span>).</li>\n";
push @H, "<li><b>HGVSc</b> kept only where it is real HGVS; pseudo-notation such as <span class=\"mono\">135912503G&gt;A</span> was dropped in favour of the genomic coordinate.</li>\n";
push @H, "<li><b>gnomAD AF</b> rounded to three significant figures, removing float noise (<span class=\"mono\">2.499999936844688e-06</span> &rarr; <span class=\"mono\">2.5e-06</span>).</li>\n";
push @H, "<li><b>ClinVar</b> synonyms merged (<span class=\"mono\">P/LP</span>, <span class=\"mono\">VUS</span>).</li>\n";
push @H, "<li><b>Null markers</b> <span class=\"mono\">missing</span>, <span class=\"mono\">.</span> and empty all treated as no data.</li>\n";
push @H, "<li><b>Dates</b> converted to ISO (<span class=\"mono\">14/08/2026</span> &rarr; <span class=\"mono\">2026-08-14</span>).</li>\n";
push @H, sprintf("<li><b>Duplicates</b> merged on sample + position + alleles: %d source rows &rarr; %d unique variants.</li>\n",
    $n_rows, scalar @order);
push @H, "</ul>\n";

push @H, qq{<h3>Flags raised while cleaning</h3>\n<ul class="why cav">\n};
push @H, '<li>' . esc($_) . "</li>\n" for @QC;
push @H, "</ul>\n";

push @H, <<"FOOT";
<div class="foot">
<p>Generated by <code>tidy_talos.pl / tidy_talos.py</code> from <code>$IN</code> on $now.
Assembly ($ASSEMBLY) is inferred from the coordinates, not declared in the source file &mdash;
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
FOOT

open my $html, '>', "$OUTDIR/talos_case_report.html" or die $!;
print $html join('', @H);
close $html;

printf "read %d rows -> %d unique variants across %d cases\n",
    $n_rows, scalar(@order), scalar(keys %by_sample);
printf "wrote %s/talos_candidates_tidy.tsv\n", $OUTDIR;
printf "wrote %s/talos_case_report.html\n", $OUTDIR;
printf "wrote %s/talos_cleaning_log.txt (%d notes)\n", $OUTDIR, scalar @QC;
