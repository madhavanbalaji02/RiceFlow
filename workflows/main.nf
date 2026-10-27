nextflow.enable.dsl=2
include { COHORT_QC } from '../modules/cohort'
include { VCF_QC } from '../modules/vcf'

process COLLECT {
    publishDir params.outdir, mode: 'copy', overwrite: false
    input:
    path cohort
    path vcf
    val inject_failure
    output:
    path 'cohort', emit: cohort
    path 'vcf', emit: vcf
    script:
    """
    if [ '${inject_failure}' = 'true' ]; then
      echo 'Intentional failure after both scientific tasks completed' >&2
      exit 42
    fi
    test -s cohort/summary.json
    test -s vcf/summary.json
    """
}

process VCF_BLOCKED {
    output:
    path 'vcf', emit: result
    script:
    """
    mkdir vcf
    echo '{"status":"BLOCKED","reason":"Compatible authoritative FASTA could not be retrieved with verified TLS. No real VCF quality validation claimed."}' > vcf/summary.json
    """
}

workflow {
    cfg = new groovy.json.JsonSlurper().parse(file(params.config_json).toFile())
    COHORT_QC(file(cfg.cohort + '.bed', checkIfExists:true), file(cfg.cohort + '.bim', checkIfExists:true),
              file(cfg.cohort + '.fam', checkIfExists:true), groovy.json.JsonOutput.toJson(cfg.policy),
              groovy.json.JsonOutput.toJson([chrom:cfg.chrom, start:cfg.start, end:cfg.end,
                                            sample_count:cfg.sample_count, input_sha256:cfg.input_sha256]))
    if (cfg.vcf && cfg.reference) {
        VCF_QC(file(cfg.vcf, checkIfExists:true), file(cfg.reference, checkIfExists:true),
               file(cfg.reference + '.fai', checkIfExists:true), groovy.json.JsonOutput.toJson(cfg.policy), cfg.expected_sample,
               groovy.json.JsonOutput.toJson(cfg.input_sha256))
        vcf_result = VCF_QC.out.result
    } else {
        VCF_BLOCKED()
        vcf_result = VCF_BLOCKED.out.result
    }
    COLLECT(COHORT_QC.out.result, vcf_result, params.inject_failure)
}
