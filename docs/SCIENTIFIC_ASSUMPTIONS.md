# Scientific scope and assumptions

Rice is modeled as diploid with 12 autosomes and no sex/mitochondrial chromosome codes in this release.
Unexpected contigs, ambiguous alleles, duplicate/conflicting positions, non-diploid calls, malformed
binary dimensions, and reference mismatches fail validation. Numeric source variant IDs need not be
unique across chromosomes. Contig names are never silently renamed to satisfy reference checks.

The CoreSNP source is already selected and LD-pruned. This demonstration examines missingness,
allele counts and descriptive heterozygosity on a deterministic small downstream subset. It cannot
assess original read depth, variant-calling sensitivity, population LD or genome-wide cohort quality.
The sample ordering is lexical FID then IID; interval endpoints are inclusive. Selection is reproducible,
not representative sampling and not evidence of a population-level biological finding.

Quality masking occurs first in the individual-VCF track, then sample assessment and exclusion, then
site metric recomputation. Reference records are counted but are outside biallelic SNP QC. Unsupported
alleles are explicit scope exclusions. Partial GTs count as uncalled and do not contribute half an
allele denominator. Absent records remain unknown. Individual accession observations are never joined
by substituting reference GTs and never called a jointly genotyped cohort.

Default analysis choices: sample call rate 0.8, site call rate 0.9, DP >=5, GQ disabled, missing enabled
quality not_assessed and masked, MAF >=0. The tiny fixture demo uses sample call rate 0.4 deliberately
to retain its sample with many constructed failures. No HWE threshold is used for this crop dataset.
Sensitivity grids are descriptive threshold comparisons on the same inputs; they do not optimize
accuracy or justify a chosen cutoff. All choices belong in the run manifest.

Imputation remains unimplemented and disabled. Future work requires compatible independent panels,
explicit panel/evaluation separation, reproducible held-out genotype masking, crop-appropriate models,
leakage checks and a baseline comparison before any accuracy claim. Pangenome construction and
haplotype expansion are outside this release.
