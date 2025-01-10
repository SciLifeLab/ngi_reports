"""Module for producing the ONT Project Summary Report"""

import os
import ngi_reports.reports.project_summary

from collections import OrderedDict
from string import ascii_uppercase as alphabets


class Report(ngi_reports.reports.project_summary.Report):
    def __init__(self, LOG, working_dir, **kwargs):
        super(Report, self).__init__(LOG, working_dir, **kwargs)

    def generate_report_template(self, proj, template, support_email):
        if not self.signature:
            self.LOG.error(
                "It is required to provide Signature/Name while generating 'project_summary' report, see -s opition in help"
            )
            raise SystemExit
        else:
            self.report_info["signature"] = self.signature

        seq_methods = OrderedDict()

        # Get information for the report
        self.report_basename = proj.ngi_name
        self.report_info["support_email"] = support_email
        self.report_info["dates"] = self.get_order_dates(proj.dates)
        self.report_info["report_date"] = self.creation_date

        # Get sequecing method for the flowcell
        seq_template = (
            "{}) Samples were sequenced on {}, flowcell type {}, MinKNOW version {}. Basecalling was performed "
            "using Guppy version {}, {} model. The quality scale used is Phred and the quality score threshold is {}."
        )

        # Collect required information for all flowcells run for the project
        for fc in proj.flowcells.values():
            tmp_method = seq_template.format(
                "SECTION",
                fc.type,
                fc.fc_type,
                fc.seq_software.get("MinKNOW version"),
                fc.seq_software.get("Guppy version"),
                fc.basecall_model,
                fc.qual_threshold,
            )

            # To make sure the sequencing methods are unique
            if tmp_method not in list(seq_methods.keys()):
                seq_methods[tmp_method] = alphabets[len(list(seq_methods.keys()))]
            fc.seq_meth = seq_methods[tmp_method]

        # Give proper section name for the methods
        self.report_info["sequencing_methods"] = "\n\n".join(
            [m.replace("SECTION", seq_methods[m]) for m in seq_methods]
        )

        # Check if sequencing info is complete
        if not self.report_info["sequencing_methods"]:
            self.LOG.warn(
                "Sequencing methods may have some missing information, kindly check your inputs."
            )

        ###############################################################################
        ##### Create table text and header explanation from collected information #####
        ###############################################################################
        # sample_info table
        unit_magnitude = {"#reads": "", "Kreads": "Thousand", "Mreads": "Million"}
        sample_header = ["NGI ID", "User ID", proj.samples_unit]
        sample_filter = ["ngi_id", "customer_name", "total_reads"]
        self.tables_info["tables"]["sample_info"] = self.create_table_text(
            proj.samples.values(), filter_keys=sample_filter, header=sample_header
        )
        self.tables_info["header_explanation"]["sample_info"] = (
            "* _NGI ID:_ Internal NGI sample identifier\n"
            "* _User ID:_ Sample name submitted by user\n"
            "* _{}:_ Number of reads per sample ({})\n".format(
                proj.samples_unit, unit_magnitude[proj.samples_unit]
            )
        )

        # library_info table
        library_header = ["NGI ID", "Index", "Avg. FS(bp)", "Lib. QC"]
        library_filter = ["ngi_id", "barcode", "avg_size", "qc_status"]
        library_list = []
        for s, v in list(proj.samples.items()):
            for p in list(v.preps.values()):
                p = vars(p)
                p["ngi_id"] = s
                if len(proj.samples.items()) == 1 and p.get("barcode") == "NA":
                    p["barcode"] = "no index"
                library_list.append(p)
        self.tables_info["tables"]["library_info"] = self.create_table_text(
            sorted(library_list, key=lambda d: d["ngi_id"]),
            filter_keys=library_filter,
            header=library_header,
        )
        self.tables_info["header_explanation"]["library_info"] = (
            "* _NGI ID:_ Internal NGI sample identifier\n"
            "* _Index:_ Barcode sequence used for the sample\n"
            "* _Avg. FS:_ Average fragment size of the library\n"
            "* _Lib. QC:_ Library quality control status\n"
        )

        # lanes_info table
        lanes_header = ["Date", "Flow cell", "Reads (M)", "N50"]
        lanes_filter = ["date", "name", "reads", "n50"]
        lanes_list = []
        for f, v in list(proj.flowcells.items()):
            lane = {}
            lane["date"] = v.date
            lane["name"] = v.run_name
            lane["reads"] = v.total_reads
            lane["n50"] = v.n50
            lanes_list.append(lane)
        self.tables_info["tables"]["lanes_info"] = self.create_table_text(
            sorted(lanes_list, key=lambda d: d["date"]),
            filter_keys=lanes_filter,
            header=lanes_header,
        )
        self.tables_info["header_explanation"]["lanes_info"] = (
            "* _Date:_ Date of sequencing\n"
            "* _Flow cell:_ Flow cell identifier\n"
            "* _Reads (M):_ Number of reads generated (million)\n"
            "* _N50:_ Estimated N50\n"
        )
        # TODO: Add lists of samples for each FC
        # Make the file basename
        output_bn = os.path.realpath(
            os.path.join(
                self.working_dir,
                self.report_dir,
                "{}_project_summary".format(self.report_basename),
            )
        )

        # Parse the template
        try:
            md = template.render(
                project=proj,
                tables=self.tables_info["header_explanation"],
                report_info=self.report_info,
            )
            return {output_bn: md}
        except:
            self.LOG.error("Could not parse the project_summary template")
            raise
