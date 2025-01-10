"""Define various entities and populate them"""

import re
import sys
import numpy as np
from collections import defaultdict, OrderedDict
from datetime import datetime

from ngi_reports.utils import statusdb


class Sample:
    """Sample class"""

    def __init__(self):
        self.customer_name = ""
        self.ngi_id = ""
        self.preps = {}
        self.qscore = ""
        self.total_reads = 0.0
        self.initial_qc = {
            "initial_qc_status": "",
            "concentration": "",
            "conc_units": "",
            "volume_(ul)": "",
            "amount_(ng)": "",
            "rin": "",
        }
        self.well_location = ""


class Prep:
    """Prep class"""

    def __init__(self):
        self.avg_size = "NA"
        self.barcode = "NA"
        self.label = ""
        self.qc_status = "NA"
        self.seq_fc = "NA"


class Flowcell:
    """Flowcell class"""

    def __init__(self):
        self.date = ""
        self.lanes = OrderedDict()
        self.name = ""
        self.run_name = ""
        self.run_setup = []
        self.seq_meth = ""
        self.type = ""
        self.run_params = {}
        self.chemistry = {}
        self.casava = None
        self.seq_software = {}


class Lane:
    """Lane class"""

    def __init__(self):
        self.avg_qval = ""
        self.cluster = ""
        self.id = ""
        self.phix = ""
        self.weighted_avg_qval_proj = 0
        self.total_reads_proj = 0
        self.total_reads_with_qval_proj = 0
        self.reads_unit = "#reads"

    def set_lane_info(self, to_set, key, lane_info, reads, as_million=False):
        """Set the average value of gives key from given lane info
        :param str to_set: class parameter to be set
        :param str key: key to be fetched
        :param dict lane_info: a dictionary with required lane info
        :param str reads: number of reads for keys to be fetched
        """
        try:
            v = np.mean(
                [
                    float(lane_info.get("{} R{}".format(key, str(r))))
                    for r in range(1, int(reads) + 1)
                ]
            )
            val = (
                "{:.2f}".format(round(v / 1000000, 2))
                if as_million
                else "{:.2f}".format(round(v, 2))
            )
        except TypeError:
            val = None

        if to_set == "cluster":
            self.cluster = val
        elif to_set == "avg_qval":
            self.avg_qval = val
        elif to_set == "fc_phix":
            self.phix = val


class AbortedSampleInfo:
    """Aborted Sample info class"""

    def __init__(self, user_id, status):
        self.status = status
        self.user_id = user_id


class Project:
    """Project class"""

    def __init__(self):
        self.aborted_samples = OrderedDict()
        self.samples = OrderedDict()
        self.flowcells = {}
        self.accredited = {
            "library_preparation": "N/A",
            "data_processing": "N/A",
            "sequencing": "N/A",
            "data_analysis": "N/A",
        }
        self.application = ""
        self.best_practice = False
        self.cluster = ""
        self.contact = ""
        self.dates = {
            "order_received": None,
            "open_date": None,
            "first_initial_qc_start_date": None,
            "contract_received": None,
            "samples_received": None,
            "queue_date": None,
            "all_samples_sequenced": None,
        }
        self.is_finished_lib = False
        self.is_hiseqx = False
        self.library_construction = ""
        self.missing_fc = False
        self.ngi_facility = ""
        self.ngi_name = ""
        self.samples_unit = "#reads"
        self.num_samples = 0
        self.num_lanes = 0
        self.ngi_id = ""
        self.reference = {"genome": None, "organism": None}
        self.report_date = ""
        self.sequencing_setup = ""
        self.skip_fastq = False
        self.user_ID = ""

    def populate(self, log, organism_names, **kwargs):
        project = kwargs.get("project", "")
        if not project:
            log.error("A project must be provided, so not proceeding.")
            sys.exit("A project was not provided, stopping execution...")
        self.skip_fastq = kwargs.get("skip_fastq")
        self.cluster = kwargs.get("cluster")

        pcon = statusdb.ProjectSummaryConnection()
        assert pcon, "Could not connect to {} database in StatusDB".format("project")

        if re.match("^P\d+$", project):
            self.ngi_id = project
            id_view = True
        else:
            self.ngi_name = project
            id_view = False

        proj = pcon.get_entry(project, use_id_view=id_view)
        if not proj:
            log.error(
                'No such project name/id "{}", check if provided information is right'.format(
                    project
                )
            )
            sys.exit("Project not found in statusdb, stopping execution...")
        self.ngi_name = proj.get("project_name")

        if proj.get("source") != "lims":
            log.error("The source for data for project {} is not LIMS.".format(project))
            raise BaseException

        proj_details = proj.get("details", {})

        if "aborted" in proj_details:
            log.warn("Project {} was aborted, so not proceeding.".format(project))
            sys.exit("Project {} was aborted, stopping execution...".format(project))

        if not id_view:
            self.ngi_id = proj.get("project_id")

        for date in self.dates:
            self.dates[date] = proj_details.get(date, None)

        if proj.get("project_summary", {}).get("all_samples_sequenced"):
            self.dates["all_samples_sequenced"] = proj.get("project_summary", {}).get(
                "all_samples_sequenced"
            )

        self.contact = proj.get("order_details", {}).get("owner", {}).get("email", "NA")
        self.application = proj.get("application")
        self.num_samples = proj.get("no_of_samples")
        self.ngi_facility = (
            "Genomics {} Stockholm".format(proj_details.get("type"))
            if proj_details.get("type")
            else None
        )
        self.reference["genome"] = (
            None
            if proj.get("reference_genome") == "other"
            else proj.get("reference_genome")
        )
        self.reference["organism"] = organism_names.get(self.reference["genome"], None)
        self.user_ID = proj_details.get("customer_project_reference", "")
        self.num_lanes = proj_details.get("sequence_units_ordered_(lanes)")
        self.library_construction_method = proj_details.get(
            "library_construction_method"
        )
        self.library_prep_option = proj_details.get("library_prep_option", "")

        if "dds" in proj.get("delivery_type", "").lower():
            self.cluster = "dds"
        elif "hdd" in proj.get("delivery_type", "").lower():
            self.cluster = "hdd"
        else:
            self.cluster = "unknown"

        self.best_practice = (
            False
            if proj_details.get("best_practice_bioinformatics", "No") == "No"
            else True
        )
        self.library_construction = self.get_library_method(
            self.ngi_name,
            self.application,
            self.library_construction_method,
            self.library_prep_option,
        )
        self.is_finished_lib = (
            True if "by user" in self.library_construction.lower() else False
        )

        for key in self.accredited:
            self.accredited[key] = proj_details.get("accredited_({})".format(key))

        if "hiseqx" in proj_details.get("sequencing_platform", ""):
            self.is_hiseqx = True

        self.sequencing_setup = proj_details.get("sequencing_setup")

        for sample_id, sample in sorted(proj.get("samples", {}).items()):
            if kwargs.get("samples", []) and sample_id not in kwargs.get("samples", []):
                log.info(
                    "Will not include sample {} as it is not in given list".format(
                        sample_id
                    )
                )
                continue

            customer_name = sample.get("customer_name", "NA")
            # Get once for a project
            if self.dates["first_initial_qc_start_date"] is not None:
                self.dates["first_initial_qc_start_date"] = sample.get(
                    "first_initial_qc_start_date"
                )

            log.info("Processing sample {}".format(sample_id))
            # Check if the sample is aborted before processing
            if sample.get("details", {}).get("status_(manual)") == "Aborted":
                log.info("Sample {} is aborted, so skipping it".format(sample_id))
                self.aborted_samples[sample_id] = AbortedSampleInfo(
                    customer_name, "Aborted"
                )
                continue

            samObj = Sample()
            samObj.ngi_id = sample_id
            samObj.customer_name = customer_name
            samObj.well_location = sample.get("well_location")
            # Basic fields from Project database
            # Initial qc
            if sample.get("initial_qc"):
                for item in samObj.initial_qc:
                    samObj.initial_qc[item] = sample["initial_qc"].get(item)
                    if (
                        item == "initial_qc_status"
                        and sample["initial_qc"]["initial_qc_status"] == "UNKNOWN"
                    ):
                        samObj.initial_qc[item] = "NA"

            # Library prep
            # Get total reads if available or mark sample as not sequenced
            try:
                # Check if sample was sequenced. More accurate value will be calculated from flowcell yield
                total_reads = float(sample["details"]["total_reads_(m)"])
            except KeyError:
                log.warn(
                    "Sample {} doesnt have total reads, so adding it to NOT sequenced samples list.".format(
                        sample_id
                    )
                )
                self.aborted_samples[sample_id] = AbortedSampleInfo(
                    customer_name, "Not sequenced"
                )
                # Don't gather unnecessary information if not going to be looked up
                if not kwargs.get("yield_from_fc"):
                    continue

            # Go through each prep for each sample in the Projects database
            for prep_id, prep in list(sample.get("library_prep", {}).items()):
                prepObj = Prep()

                prepObj.label = "Lib. " + prep_id
                if "by user" in self.library_construction.lower():
                    prepObj.label = "NA"

                prepObj.barcode = prep.get("reagent_label", "NA")
                prepObj.qc_status = prep.get("prep_status", "NA")

                if prepObj.barcode == "NA":
                    log.warn(
                        f"Barcode missing for sample {sample_id} in prep {prep_id}. This could be a NOINDEX case, please check the report."
                    )
                if prepObj.qc_status == "NA":
                    log.warn(
                        f"Prep status missing for sample {sample_id} in prep {prep_id}"
                    )
                # Get flow cell information for each prep from project database (only if -b flag is set)
                if prepObj.barcode != "NA" and prepObj.qc_status != "NA":
                    if kwargs.get("barcode_from_fc"):
                        prepObj.seq_fc = []
                        if (
                            not sample.get("library_prep")
                            .get(prep_id)
                            .get("sequenced_fc")
                        ):
                            log.error(
                                'Sequenced flowcell not defined for the project. Run ngi_pipelines without the "-b" flag and amend the report manually.'
                            )
                            sys.exit("Stopping execution...")
                        for fc in (
                            sample.get("library_prep").get(prep_id).get("sequenced_fc")
                        ):
                            prepObj.seq_fc.append(fc.split("_")[-1])

                if "pcr-free" not in self.library_construction.lower():
                    if prep.get("library_validation"):
                        lib_valids = prep["library_validation"]
                        keys = sorted(
                            [
                                k
                                for k in list(lib_valids.keys())
                                if re.match("^[\d\-]*$", k)
                            ],
                            key=lambda k: datetime.strptime(
                                lib_valids[k]["start_date"], "%Y-%m-%d"
                            ),
                            reverse=True,
                        )
                        try:
                            prepObj.avg_size = re.sub(
                                r"(\.[0-9]{,2}).*$",
                                r"\1",
                                str(lib_valids[keys[0]]["average_size_bp"]),
                            )
                        except:
                            log.warn(
                                'Insufficient info "{}" for sample {}'.format(
                                    "average_size_bp", sample_id
                                )
                            )
                    else:
                        log.warn(
                            "No library validation step found {}".format(sample_id)
                        )

                samObj.preps[prep_id] = prepObj

            # Exception for case of multi-barcoded sample from different preps run on the same fc (only if -b flag is set)
            if kwargs.get("barcode_from_fc"):
                list_of_barcodes = sum(
                    [
                        [
                            all_barcodes.barcode
                            for all_barcodes in list(samObj.preps.values())
                        ]
                    ],
                    [],
                )
                if len(list(dict.fromkeys(list_of_barcodes))) >= 1:
                    list_of_flowcells = sum(
                        [
                            all_flowcells.seq_fc
                            for all_flowcells in list(samObj.preps.values())
                        ],
                        [],
                    )
                    if (
                        len(list_of_flowcells)
                        != len(list(dict.fromkeys(list_of_flowcells)))
                    ):  # The sample was run twice on the same flowcell, only possible with different barcodes for the same sample
                        log.error(
                            "Ambiguous preps for barcodes on flowcell. Please run ngi_pipelines without the -b flag and amend the report manually"
                        )
                        sys.exit("Stopping execution...")
                else:
                    log.error(
                        "Barcodes not defined in sample sheet. Please run ngi_pipelines without the -b flag and amend the report manually"
                    )
                    sys.exit("Stopping execution...")

            if not samObj.preps:
                log.warn(
                    "No library prep information was available for sample {}".format(
                        sample_id
                    )
                )
            self.samples[sample_id] = samObj

        # Get Flowcell data
        fcon = statusdb.FlowcellRunMetricsConnection()
        assert fcon, "Could not connect to {} database in StatusDB".format("flowcell")
        xcon = statusdb.X_FlowcellRunMetricsConnection()
        assert xcon, "Could not connect to {} database in StatusDB".format(
            "x_flowcells"
        )
        ontcon = statusdb.NanoporeRunConnection()
        assert ontcon, "Could not connect to {} database in StatusDB".format(
            "nanopore_runs"
        )
        flowcell_info = fcon.get_project_flowcell(self.ngi_id, self.dates["open_date"])
        flowcell_info.update(
            xcon.get_project_flowcell(self.ngi_id, self.dates["open_date"])
        )
        flowcell_info.update(
            ontcon.get_project_flowcell(self.ngi_id, self.dates["open_date"])
        )

        sample_qval = defaultdict(dict)
        sample_stats = defaultdict(dict)

        for fc in list(flowcell_info.values()):
            if fc["name"] in kwargs.get("exclude_fc"):
                continue
            fcObj = Flowcell()
            fcObj.name = fc["name"]
            fcObj.run_name = fc["run_name"]
            fcObj.date = fc["date"]

            # Get database document from appropriate database
            if fc["db"] == "x_flowcells":
                fc_details = xcon.get_entry(fc["run_name"])
            elif fc["db"] == "nanopore_runs":
                fc_details = ontcon.get_entry(fc["run_name"])
            else:
                fc_details = fcon.get_entry(fc["run_name"])

            # Set the fc type
            fc_instrument = fc_details.get("RunInfo", {}).get("Instrument", "")
            if fc_instrument.startswith("ST-"):
                fcObj.type = "HiSeqX"
                self.is_hiseqx = True
                fc_runparameters = fc_details.get("RunParameters", {}).get("Setup", {})
            elif "-" in fcObj.name:
                fcObj.type = "MiSeq"
                fc_runparameters = fc_details.get("RunParameters", {})
            elif fc_instrument.startswith("A"):
                fcObj.type = "NovaSeq6000"
                fc_runparameters = fc_details.get("RunParameters", {})
            elif fc_instrument.startswith("LH"):
                fcObj.type = "NovaSeqXPlus"
                fc_runparameters = fc_details.get("RunParameters", {})
            elif fc_instrument.startswith("NS"):
                fcObj.type = "NextSeq500"
                fc_runparameters = fc_details.get("RunParameters", {})
            elif fc_instrument.startswith("VH"):
                fcObj.type = "NextSeq2000"
                fc_runparameters = fc_details.get("RunParameters", {})
            elif "_PA" in fcObj.run_name:
                fcObj.type = "PromethION"
                fc_runparameters = fc_details.get("protocol_run_info", {})
                final_acquisition = fc_details.get("acquisitions")[-1]
            elif "_MN" in fcObj.run_name:
                fcObj.type = "MinION"
                fc_runparameters = fc_details.get("protocol_run_info", {})
                final_acquisition = fc_details.get("acquisitions")[-1]
            else:
                fcObj.type = "HiSeq2500"
                fc_runparameters = fc_details.get("RunParameters", {}).get("Setup", {})

            # Fetch run setup for the flowcell
            if fcObj.type == "PromethION" or fcObj.type == "MinION":
                fcObj.fc_type = fc_runparameters.get("flow_cell").get(
                    "user_specified_product_code"
                )  # product_code not specified for minion
                run_arguments = fc_runparameters.get("args")
                for arg in run_arguments:
                    if "min_qscore" in arg:
                        fcObj.qual_threshold = float(arg.split("=")[-1])
                fcObj.n50 = float(
                    final_acquisition.get("read_length_histogram")[-1]
                    .get("plot")
                    .get("histogram_data")[0]
                    .get("n50")
                )
                fcObj.total_reads = float(
                    final_acquisition.get("acquisition_run_info")
                    .get("yield_summary")
                    .get("read_count")
                )
                fcObj.total_reads = round(fcObj.total_reads / 1000000, 2)
                # TODO: get list of samples per FC and avg read length here once implemented in TACA

            else:
                fcObj.run_setup = fc_details.get("RunInfo").get("Reads")

            if fcObj.type == "NovaSeq6000":
                fcObj.chemistry = {
                    "WorkflowType": fc_runparameters.get("WorkflowType"),
                    "FlowCellMode": fc_runparameters.get("RfidsInfo", {}).get(
                        "FlowCellMode"
                    ),
                }
            elif fcObj.type == "NovaSeqXPlus":
                fcObj.chemistry = {"RecipeName": fc_runparameters.get("RecipeName")}
            elif fcObj.type == "NextSeq500":
                fcObj.chemistry = {
                    "Chemistry": fc_runparameters.get("Chemistry").replace(
                        "NextSeq ", ""
                    )
                }
            elif fcObj.type == "NextSeq2000":
                NS2000_FC_PAT = re.compile("P[1,2,3]")
                fcObj.chemistry = {
                    "Chemistry": NS2000_FC_PAT.findall(
                        fc_runparameters.get("FlowCellMode")
                    )[0]
                }
            else:
                fcObj.chemistry = {
                    "Chemistry": fc_runparameters.get(
                        "ReagentKitVersion", fc_runparameters.get("Sbs")
                    )
                }

            if fcObj.type != "PromethION" and fcObj.type != "MinION":
                try:
                    fcObj.casava = list(fc_details["DemultiplexConfig"].values())[0][
                        "Software"
                    ]["Version"]
                except (KeyError, IndexError):
                    continue

            if fcObj.type == "MiSeq":
                fcObj.seq_software = {
                    "RTAVersion": fc_runparameters.get("RTAVersion"),
                    "ApplicationVersion": fc_runparameters.get("MCSVersion"),
                }
            elif fcObj.type == "NextSeq500" or fcObj.type == "NextSeq2000":
                fcObj.seq_software = {
                    "RTAVersion": fc_runparameters.get(
                        "RTAVersion", fc_runparameters.get("RtaVersion")
                    ),
                    "ApplicationName": fc_runparameters.get("ApplicationName")
                    if fc_runparameters.get("ApplicationName")
                    else fc_runparameters.get("Setup").get("ApplicationName"),
                    "ApplicationVersion": fc_runparameters.get("ApplicationVersion")
                    if fc_runparameters.get("ApplicationVersion")
                    else fc_runparameters.get("Setup").get("ApplicationVersion"),
                }
            elif fcObj.type == "NovaSeqXPlus":
                fcObj.seq_software = {
                    "ApplicationName": fc_runparameters.get("Application"),
                    "ApplicationVersion": fc_runparameters.get("SystemSuiteVersion"),
                }
            elif fcObj.type == "PromethION" or fcObj.type == "MinION":
                ont_seq_versions = fc_runparameters.get("software_versions", "")
                fcObj.seq_software = {
                    "MinKNOW version": ont_seq_versions.get("minknow", "").get(
                        "full", ""
                    ),
                    "Guppy version": ont_seq_versions.get("guppy_build_version", ""),
                }
                fcObj.basecall_model = (
                    fc_runparameters.get("meta_info", "")
                    .get("tags", "")
                    .get("default basecall model")
                    .get("string_value")
                )
            else:
                fcObj.seq_software = {
                    "RTAVersion": fc_runparameters.get(
                        "RTAVersion", fc_runparameters.get("RtaVersion")
                    ),
                    "ApplicationName": fc_runparameters.get(
                        "ApplicationName", fc_runparameters.get("Application")
                    ),
                    "ApplicationVersion": fc_runparameters.get("ApplicationVersion"),
                }

            # Collect info of samples and their library prep / LIMS indexes on the FC (only if -b option is set)
            if kwargs.get("barcode_from_fc"):
                log.info(
                    "'barcodes_from_fc' option was given so index sequences for the report will be taken from the flowcell instead of LIMS"
                )
                preps_samples_on_fc = []
                list_additional_samples = []

                # Get all samples from flow cell that belong to the project
                fc_samples = []
                for fc_sample in fc_details.get("samplesheet_csv"):
                    if fc_sample.get("Sample_Name").split("_")[0] == self.ngi_id:
                        fc_samples.append(fc_sample.get("Sample_Name"))

                # Iterate through all samples in project to identify their prep_ID (only if they are on the flowcell)
                for sample_ID in list(self.samples):
                    for prep_ID in list(self.samples.get(sample_ID).preps):
                        sample_preps = self.samples.get(sample_ID).preps
                        if fcObj.name in sample_preps.get(prep_ID).seq_fc:
                            preps_samples_on_fc.append([sample_ID, prep_ID])
                        else:
                            continue

                # Get (if any) samples that are on the fc, but are not recorded in LIMS (i.e. added bc from undet reads)
                if len(set(list(self.samples))) != len(set(fc_samples)):
                    list_additional_samples = list(set(fc_samples) - set(self.samples))
                    list_additional_samples.sort()
                    log.info(
                        "The flowcell {} contains {} sample(s) ({}) that "
                        "has/have not been defined in LIMS. They will be added to the report.".format(
                            fc_details.get("RunInfo").get("Id"),
                            len(list_additional_samples),
                            ", ".join(list_additional_samples),
                        )
                    )

                    undet_iteration = 1
                    # Creating additional sample and prep Objects
                    for additional_sample in list_additional_samples:
                        AsamObj = Sample()
                        AsamObj.ngi_id = additional_sample
                        AsamObj.customer_name = (
                            "unknown" + str(undet_iteration)
                        )  # Additional samples will be named "unknown[number]" in the report
                        AsamObj.well_location = "NA"
                        AsamObj.preps["NA"] = Prep()
                        AsamObj.preps["NA"].label = "NA"
                        self.samples[additional_sample] = AsamObj
                        preps_samples_on_fc.append([additional_sample, "NA"])
                        undet_iteration += 1

            # Collect quality info for samples and collect lanes of interest (Illumina)
            for stat in (
                fc_details.get("illumina", {})
                .get("Demultiplex_Stats", {})
                .get("Barcode_lane_statistics", [])
            ):
                if (
                    re.sub("_+", ".", stat["Project"], 1) != self.ngi_name
                    and stat["Project"] != self.ngi_name
                ):
                    continue

                lane = stat.get("Lane")
                if fc["db"] == "x_flowcells":
                    sample = stat.get("Sample")
                    barcode = stat.get("Barcode sequence")
                    qval_key, base_key = ("% >= Q30bases", "PF Clusters")

                else:
                    sample = stat.get("Sample ID")
                    barcode = stat.get("Index")
                    qval_key, base_key = ("% of >= Q30 Bases (PF)", "# Reads")

                # If '-b' flag is set, we override the barcodes from LIMS with the barcodes from the flowcell for all samples
                if kwargs.get("barcode_from_fc"):
                    new_barcode = "-".join(
                        barcode.split("+")
                    )  # Change the barcode layout to match the one used for the report
                    lib_prep = []  # Adding the now required library prep, set to NA for all non-LIMS samples
                    if sample in list_additional_samples:
                        lib_prep.append("NA")
                    else:  # Adding library prep for LIMS samples, we identified them earlier
                        for sub_prep_sample in preps_samples_on_fc:
                            if sub_prep_sample[0] == sample:
                                lib_prep.append(sub_prep_sample[1])

                    for (
                        prep_o_samples
                    ) in lib_prep:  # Changing the barcode happens here!
                        self.samples.get(sample).preps.get(
                            prep_o_samples
                        ).barcode = new_barcode

                # Skip if there are no lanes or samples
                if not lane or not sample or not barcode:
                    log.warn(
                        "Insufficient info/malformed data in Barcode_lane_statistics in FC {}, skipping...".format(
                            fcObj.name
                        )
                    )
                    continue

                if kwargs.get("samples", []) and sample not in kwargs.get(
                    "samples", []
                ):
                    continue

                try:
                    r_idx = "{}_{}_{}".format(lane, fcObj.name, barcode)
                    r_len_list = [
                        x["NumCycles"]
                        for x in fcObj.run_setup
                        if x["IsIndexedRead"] == "N"
                    ]
                    r_len_list = [int(x) for x in r_len_list]
                    r_num = len(r_len_list)
                    qval = float(stat.get(qval_key))
                    pfrd = int(stat.get(base_key).replace(",", ""))
                    pfrd = pfrd / 2 if fc["db"] == "flowcell" else pfrd
                    base = pfrd * sum(r_len_list)
                    sample_qval[sample][r_idx] = {
                        "qval": qval,
                        "reads": pfrd,
                        "bases": base,
                    }

                except (TypeError, ValueError, AttributeError) as e:
                    log.warn(
                        "Something went wrong while fetching Q30 for sample {} with "
                        "barcode {} in FC {} at lane {}. Error was: \n{}".format(
                            sample, barcode, fcObj.name, lane, e
                        )
                    )
                    pass
                # Collect lanes of interest to proceed later
                fc_lane_summary_lims = fc_details.get("lims_data", {}).get(
                    "run_summary", {}
                )
                fc_lane_summary_demux = (
                    fc_details.get("illumina", {})
                    .get("Demultiplex_Stats", {})
                    .get("Lanes_stats", {})
                )
                if lane not in fcObj.lanes:
                    laneObj = Lane()
                    lane_sum_lims = fc_lane_summary_lims.get(
                        lane, fc_lane_summary_lims.get("A", {})
                    )
                    lane_sum_demux = [
                        d for d in fc_lane_summary_demux if d["Lane"] == str(lane)
                    ][0]
                    laneObj.id = lane
                    laneObj.cluster = "{:.2f}".format(
                        round(
                            float(
                                lane_sum_demux.get("PF Clusters", "0").replace(",", "")
                            )
                            / 1000000,
                            2,
                        )
                    )
                    laneObj.avg_qval = "{:.2f}".format(
                        round(float(lane_sum_demux.get("% >= Q30bases", "0.00")), 2)
                    )
                    laneObj.set_lane_info(
                        "fc_phix", "% Error Rate", lane_sum_lims, str(r_num)
                    )
                    if kwargs.get("fc_phix", {}).get(fcObj.name, {}):
                        laneObj.phix = kwargs.get("fc_phix").get(fcObj.name).get(lane)
                    # Calculate weighted Q30 value and add it to lane data
                    laneObj.total_reads_proj += pfrd
                    if pfrd and qval:
                        laneObj.weighted_avg_qval_proj += pfrd * qval
                        laneObj.total_reads_with_qval_proj += pfrd
                    fcObj.lanes[lane] = laneObj

                    # Check if the above created lane object has all needed info
                    for k, v in vars(laneObj).items():
                        if not v:
                            log.warn(
                                "Could not fetch {} for FC {} at lane {}".format(
                                    k, fcObj.name, lane
                                )
                            )
                # Add total reads and Q30 to lane data
                else:
                    laneObj = fcObj.lanes[lane]
                    laneObj.total_reads_proj += pfrd
                    if pfrd and qval:
                        laneObj.weighted_avg_qval_proj += pfrd * qval
                        laneObj.total_reads_with_qval_proj += pfrd
            # Add units, round off values, and add to flowcells object
            for lane in fcObj.lanes:  # TODO: check if this works for ONT
                laneObj = fcObj.lanes[lane]
                laneObj.reads_unit, lane_divisor = self.get_units_and_divisor(
                    laneObj.total_reads_proj
                )
                laneObj.total_reads_proj = round(
                    laneObj.total_reads_proj / lane_divisor, 2
                )
                laneObj.weighted_avg_qval_proj /= laneObj.total_reads_with_qval_proj
                laneObj.weighted_avg_qval_proj = round(
                    laneObj.weighted_avg_qval_proj, 2
                )

            self.flowcells[fcObj.name] = fcObj

        if not self.flowcells:
            log.warn(
                "There is no flowcell to process for project {}".format(self.ngi_name)
            )
            self.missing_fc = True

        if sample_qval and kwargs.get("yield_from_fc"):
            log.info(
                "'yield_from_fc' option was given so will compute the yield from collected flowcells"
            )
            for sample in list(self.samples.keys()):
                if sample not in list(sample_qval.keys()):
                    del self.samples[sample]

        # Calculate average Q30 over all lanes and flowcell
        max_total_reads = 0
        for sample in sorted(sample_qval.keys()):
            try:
                qinfo = sample_qval[sample]
                total_qvalsbp, total_bases, total_reads = (0, 0, 0)
                for k in qinfo:
                    total_qvalsbp += qinfo[k]["qval"] * qinfo[k]["bases"]
                    total_bases += qinfo[k]["bases"]
                    total_reads += qinfo[k]["reads"]
                avg_qval = (
                    float(total_qvalsbp) / total_bases
                    if total_bases
                    else float(total_qvalsbp)
                )
                self.samples[sample].qscore = "{:.2f}".format(round(avg_qval, 2))
                # Sample has been sequenced and should be removed from the aborted/not sequenced list
                if sample in self.aborted_samples:
                    log.info(
                        "Sample {} was sequenced, so removing it from NOT sequenced samples list".format(
                            sample
                        )
                    )
                    del self.aborted_samples[sample]
                # Get/overwrite yield from the FCs computed instead of statusDB value
                if total_reads:
                    self.samples[sample].total_reads = total_reads
                    if total_reads > max_total_reads:
                        max_total_reads = total_reads
            except (TypeError, KeyError):
                log.error(
                    "Could not calcluate average Q30 for sample {}".format(sample)
                )

        # Cut down total reads to bite sized numbers
        self.samples_unit, samples_divisor = self.get_units_and_divisor(max_total_reads)

        for sample in self.samples:
            self.samples[sample].total_reads = "{:.2f}".format(
                self.samples[sample].total_reads / float(samples_divisor)
            )

    def get_units_and_divisor(self, reads):
        """Add millions or thousands unit to reads data"""
        divisor = 1
        unit = "#reads"
        if reads > 1000:
            if reads > 1000000:
                unit = "Mreads"
                divisor = 1000000
            else:
                unit = "Kreads"
                divisor = 1000
        return (unit, divisor)

    def get_library_method(
        self,
        project_name,
        application,
        library_construction_method,
        library_prep_option,
    ):
        """Get the library construction method and return as formatted string"""
        if application == "Finished library":
            return "Library was prepared by user."
        try:
            lib_meth_pat = r"^(.*?),(.*?),(.*?),(.*?)[\[,](.*)$"  # Input, Type, Option, Category -/, doucment number
            lib_head = ["Input", "Type", "Option", "Category"]
            lib_meth = re.search(lib_meth_pat, library_construction_method)
            if lib_meth:
                lib_meth_list = lib_meth.groups()[
                    :4
                ]  # not interested in the document number
                lib_list = []
                for name, value in zip(lib_head, lib_meth_list):
                    value = value.strip()  # remove empty space(s) at the ends
                    if value == "By user":
                        return "Library was prepared by user."
                    if value and value != "-":
                        lib_list.append("* {}: {}".format(name, value))
                return "\n".join(lib_list)
            else:
                if library_prep_option:
                    return "* Method: {}\n* Option: {}".format(
                        library_construction_method, library_prep_option
                    )
                else:
                    return "* Method: {}".format(library_construction_method)
        except KeyError:
            log.error(
                "Could not find library construction method for project {} in statusDB".format(
                    project_name
                )
            )
            return None
