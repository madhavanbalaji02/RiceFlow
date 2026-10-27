#!/usr/bin/env python3
from pathlib import Path
import pysam
from riceflow.cohort import write

p = Path('tests/fixtures')
p.mkdir(parents=True, exist_ok=True)
fam = [[s, s, '0', '0', '0', '-9'] for s in ['A', 'B', 'C', 'D']]
bim = [['1', '1', '0', '1', 'G', 'A'], ['1', '2', '0', '2', 'C', 'A'],
       ['1', '3', '0', '3', 'T', 'A'], ['2', '1', '0', '1', 'C', 'A']]
calls = [[(0, 0), (0, 1), (1, 1), (None, None)],
         [(0, 0), (0, 0), (0, 1), (None, None)],
         [(1, 1), (0, 1), (0, 0), (0, 0)],
         [(0, 0), (0, 1), (0, 0), (0, 0)]]
write(p / 'tiny', fam, bim, calls)
(p / 'reference.fa').write_text('>chr01\n' + 'A' * 100 + '\n')
pysam.faidx(str(p / 'reference.fa'))
header = '''##fileformat=VCFv4.2
##contig=<ID=chr01,length=100>
##FILTER=<ID=LowQual,Description="Original source filter">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Depth">
##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Quality">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1
'''
rows = [
'chr01\t1\t.\tA\t.\t.\tPASS\t.\tGT:DP\t0/0:20',
'chr01\t2\t.\tA\tG\t.\tPASS\t.\tGT:DP:GQ\t0/1:10:30',
'chr01\t3\t.\tA\tC\t.\tLowQual\t.\tGT:DP\t1/1:2',
'chr01\t4\t.\tA\tG\t.\tPASS\t.\tGT\t0/0',
'chr01\t5\t.\tA\tC\t.\tPASS\t.\tGT:DP\t./.:10',
'chr01\t6\t.\tA\tT\t.\tPASS\t.\tGT:DP\t0/.:10',
'chr01\t7\t.\tA\tAT\t.\tPASS\t.\tGT:DP\t0/1:10',
'chr01\t8\t.\tA\tG\t.\tPASS\t.\tGT:DP\t0/0:10',
'chr01\t9\t.\tA\tG\t.\tPASS\t.\tGT:DP\t1/1:10']
(p / 'tiny.vcf').write_text(header + '\n'.join(rows) + '\n')
pysam.tabix_compress(str(p / 'tiny.vcf'), str(p / 'tiny.vcf.gz'), force=True)
pysam.tabix_index(str(p / 'tiny.vcf.gz'), preset='vcf', force=True)
