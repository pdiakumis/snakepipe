version 1.0

import "tasks/count_vcf_lines.wdl" as count
import "tasks/bcftools.wdl" as bcftools
import "tasks/eval_vcf.wdl" as eval_vcf

workflow compare_vcf_files {

  input {
# sample [0], vartype [1], flabel [2], run1 [3], run2 [4]
    File inputSamplesFile

      Array[Array[File]] inputSamples = read_tsv(inputSamplesFile)
      String outdir # /abspath/to/woof/final/
#String count_outdir = outdir + "vcf_counts/"
  }

  scatter (sample in inputSamples) {
    # SNV handling
    if (sample[1] == "SNV") {
      call bcftools.filter_pass as filter_f1 { input: vcf_in = sample[3], outdir = outdir + sample[0] + "/vcf_pass/f1/" + sample[2] }
      call bcftools.filter_pass as filter_f2 { input: vcf_in = sample[4], outdir = outdir + sample[0] + "/vcf_pass/f2/" + sample[2] }

      call count.count_vars as c_all_f1 { input: vcf = sample[3], outdir = outdir + sample[0] + "/vcf_counts/f1/" + sample[2] + "/ALL/" }
      call count.count_vars as c_all_f2 { input: vcf = sample[4], outdir = outdir + sample[0] + "/vcf_counts/f2/" + sample[2] + "/ALL/"}
      call count.count_vars as c_pass_f1 { input: vcf = filter_f1.out, outdir = outdir + sample[0] + "/vcf_counts/f1/" + sample[2] + "/PASS/" }
      call count.count_vars as c_pass_f2 { input: vcf = filter_f2.out, outdir = outdir + sample[0] + "/vcf_counts/f2/" + sample[2] + "/PASS/" }

      call bcftools.isec as isec_all  { input: outdir = outdir + sample[0] + "/bcftools_isec/" + sample[2] + "/ALL", vcf1 = sample[3], vcf2 = sample[4] }
      call bcftools.isec as isec_pass { input: outdir = outdir + sample[0] + "/bcftools_isec/" + sample[2] + "/PASS", vcf1 = filter_f1.out, vcf2 = filter_f2.out }

      call eval_vcf.eval as eval_all {
        input:
          outdir = outdir + sample[0] + "/vcf_eval/" + sample[2] + "/ALL/",
               fp_vcf = isec_all.false_pos,
               fn_vcf = isec_all.false_neg,
               tp_vcf = isec_all.true_pos
      }
      call eval_vcf.eval as eval_pass {
        input:
          outdir = outdir + sample[0] + "/vcf_eval/" + sample[2] + "/PASS/",
               fp_vcf = isec_pass.false_pos,
               fn_vcf = isec_pass.false_neg,
               tp_vcf = isec_pass.true_pos
      }
    }
  }
}

