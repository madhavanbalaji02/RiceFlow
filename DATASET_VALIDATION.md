# Dataset discovery and validation

Inspected 2026-10-27. This repository began empty. Validation precedes real analysis.
Machine-readable evidence: `data/real/source-manifest.json` (copied into reports for delivery).

| Input | Actual evidence | Status |
|---|---|---|
| CoreSNP BED/BIM/FAM | All three compressed files downloaded, gzip CRC verified on decompression, SHA256 on compressed and decompressed files; 3,024 unique FID/IID pairs, 404,388 loci, chromosomes 1–12; SNP-major BED 305,717,331 bytes = 3 + 404,388 × ceil(3024/4); valid signature/padding; no duplicate loci or IDs | VERIFIED |
| B001 VCF | Content-Range total 2,187,654,873 bytes; colocated TBI parsed; chr01:10000–11000 retrieved via indexed chunks; 1,001 records, one sample B001, diploid GT, all reference calls, FORMAT GT:DP; header declares AD/DP/GQ/GT/PL | RETRIEVED, reference validation BLOCKED |
| Compatible FASTA | Official project README explicitly names RAP-DB IRGSP-1.0 and MSU release 7; authoritative RAP-DB HTTPS request fails local certificate-chain verification | BLOCKED |

Full BED gzip SHA256: `bc0d092504d2b349c1714710501531b3434fb5c602f30ebf2f0c16c1f3754382`.
BIM gzip: `ccdcc75790bcaba1bdb4b13c9b133bfa28a2966bbcde159ee62ff187e3526ee9`.
FAM gzip: `ded6261e398e73e311ad8613dffbea8acc1b1a68f3066a9e072150577687ec00`.
The full multi-gigabyte VCF was NOT downloaded and has no claimed full SHA256.

Full-transfer budget defaults to 500 MiB, regional byte budget to 16 MiB and 100 HTTP requests total,
30-second socket timeout, at most three attempts, bounded exponential backoff. Retry payload bytes count.
Requests with absent Content-Length are refused. Range requests require HTTP 206 and matching
Content-Range; a server returning 200 is rejected before reading its body. Index bytes count as full
transfers. Regional retrieval parses TBI bins and fetches BGZF blocks, filters POS to a one-based
inclusive interval, then writes an ordinary local regional VCF. It does not fill absent positions.
Header retrieval is capped at 256 KiB; per chunk at most the indexed span plus one 64-KiB BGZF block.
Request evidence, consumed bytes, source modification dates, and checksums are in the manifest.
The compressed cohort files consume approximately 115 MiB; initial VCF ranges consumed 415,530 bytes.
Transport bytes for TLS/HTTP headers are not included in payload budgets.

CoreSNP is already filtered and LD-pruned. This is downstream QC, not original variant discovery.
BIM allele order carries no independently established REF/ALT orientation. No cohort VCF is exported.
Use 12 diploid autosomes (`--chr-set 12 no-x no-y no-xy no-mt`); PLINK's `--rice` preset uses a
haploid convention unsuitable for this diploid descriptive analysis.

Official sources checked:
- https://registry.opendata.aws/3kricegenome/ (Toronto Statement usage terms and attribution)
- https://3kricegenome.s3.us-east-1.amazonaws.com/3kRG_download.html
- https://iric.irri.org/resources/3krg-in-aws
- https://iric.irri.org/resources/snp-seek-datasets
- https://3kricegenome.s3.amazonaws.com/README-rice-reference-genomes-used.txt
- https://rapdb.dna.affrc.go.jp/download/irgsp1.html (access blocked)

No accession substitution. No TLS verification bypass. Matching chr01 length alone does not prove
reference identity. Real VCF quality analysis must remain BLOCKED until authoritative reference retrieval,
sequence identity documentation, indexing, contig compatibility, and observed REF base checks succeed.
Synthetic FASTA/VCF fixtures exercise this gate offline and are explicitly labeled SYNTHETIC.

Additional bounded semantic check: chr01:1000000–1001000 contains 1,000 reference records and
one nonreference record, with both `GT:DP` and `GT:AD:DP:GQ:PL`. Its 423,473 VCF range bytes plus
339,302-byte index are separately recorded in `reports/additional-region-evidence.json`. This discovery
check does not replace the configured QC interval or establish matching reference bases. The regional
VCF extracts and official usage statements are preserved in `reports/data-evidence/` for inspection.
The official bucket's BAM/VCF and SNP usage READMEs both require the spirit of the Toronto Statement.
