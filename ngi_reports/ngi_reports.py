#!/usr/bin/env python

"""This is the entry point for ngi_reports."""

from __future__ import print_function

import argparse
import jinja2
import json
import os
import markdown
import sys

from ngi_reports import __version__
from ngi_reports.log import loggers
from ngi_reports.utils import config as report_config
from ngi_reports.utils.entities import Project

LOG = loggers.minimal_logger("NGI Reports")

## CONSTANTS
# create choices for report type based on available report template
allowed_report_types = [
    fl.replace(".md", "")
    for fl in os.listdir(
        os.path.realpath(
            os.path.join(
                os.path.dirname(__file__), os.pardir, "data", "report_templates"
            )
        )
    )
] + ["ign_aggregate_report"]


def proceed_or_not(question):
    yes = set(["yes", "y", "ye", "Y", "YES", "YE", "Yes"])
    no = set(["no", "n", "N", "NO", "No"])
    sys.stdout.write("{}".format(question))
    while True:
        choice = input().lower()
        if choice in yes:
            return True
        elif choice in no:
            return False
        else:
            sys.stderr.write("Please respond with 'yes' or 'no' ")


def make_reports(report_type, working_dir=os.getcwd(), config_file=None, **kwargs):
    # Setup
    template_fn = "{}.md".format(report_type)
    LOG.info("Report type: {}".format(report_type))

    # use default config or override it if file is specified
    config = report_config.load_config(config_file)

    # Import the modules for this report type
    report_mod = __import__(
        "ngi_reports.reports.{}".format(report_type), fromlist=["ngi_reports.reports"]
    )

    proj = Project()
    proj.populate(LOG, config._sections["organism_names"], **kwargs)

    # Make the report object
    report = report_mod.Report(LOG, working_dir, **kwargs)

    # Work out all of the directory names
    output_dir = os.path.realpath(os.path.join(working_dir, report.report_dir))
    reports_dir = os.path.realpath(
        os.path.join(os.path.dirname(__file__), os.pardir, "data", "report_templates")
    )
    working_base_dir = os.path.split(os.getcwd())[1]

    # check if the current dir is correct
    if not working_base_dir == report.project:
        question = f"The current directory {working_dir} does not belong to the chosen project {report.project}. Continue? "
        if proceed_or_not(question):
            LOG.info(
                "The reports for project {} will be generated in the current directory {}".format(
                    report.project, working_dir
                )
            )
        else:
            LOG.error(
                "Exiting the script as the current directory does not belong to the chosen project!"
            )
            sys.exit(1)
    else:
        LOG.info(
            "The reports for project {} will be generated in the current directory {}".format(
                report.project, working_dir
            )
        )

    # Create the directory if we don't already have it
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Print the markdown output file
    # Load the Jinja2 template
    try:
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(reports_dir))
        template = env.get_template("{}.md".format(report_type))
    except:
        LOG.error("Could not load the Jinja report template")
        raise

    # Change to the reports directory
    old_cwd = os.getcwd()
    os.chdir(report.report_dir)

    # Get parsed markdown and print to file(s)
    LOG.debug("Converting markdown to HTML...")
    output_mds = report.generate_report_template(
        proj, template, config.get("ngi_reports", "support_email")
    )
    for output_bn, output_md in list(output_mds.items()):
        try:
            with open("{}.md".format(output_bn), "w", encoding="utf-8") as fh:
                print(output_md, file=fh)
        except IOError as e:
            LOG.error(
                "Error printing markdown report {} - skipping. {}".format(
                    output_md, IOError(e)
                )
            )
            continue
        # Convert markdown to html
        html_out = markdown_to_html(
            report_type,
            jinja2_env=env,
            markdown_text=output_md,
            reports_dir=reports_dir,
            out_path="{}.html".format(output_bn),
        )
        LOG.info(
            "{} HTML report written to: {}".format(
                output_bn.rsplit("/", 1)[1], html_out
            )
        )

    # Generate CSV files for project_summary reports
    if (
        report_type == "project_summary"
        or report_type == "ont_project_summary"
        and not kwargs["no_txt"]
    ):
        try:
            report.create_txt_files()
            LOG.info("Generated TXT files...")
        except:
            LOG.error("Could not generate TXT files...")

    # Change back to previous working dir
    os.chdir(old_cwd)


def markdown_to_html(
    report_type,
    jinja2_env=None,
    markdown_text=None,
    markdown_path=None,
    reports_dir=None,
    out_path=None,
):
    # get path to template dir
    if not reports_dir:
        reports_dir = os.path.realpath(
            os.path.join(
                os.path.dirname(__file__), os.pardir, "data", "report_templates"
            )
        )
    # get swedac text to add to report
    with open(reports_dir + "/swedac.html", "r") as f:
        swedac_text = f.read()
    # initialise jinja env
    if not jinja2_env:
        jinja2_env = jinja2.Environment(loader=jinja2.FileSystemLoader(reports_dir))
    # get markdown text
    if not markdown_text:
        with open(markdown_path, "r") as f:
            markdown_text = f.read()

    md_template = markdown.Markdown(
        extensions=["meta", "tables", "def_list", "fenced_code", "mdx_outline"]
    )
    markeddown_text = md_template.convert(markdown_text)

    # Markdown meta returns a dict with values as lists
    html_out = jinja2_env.get_template(report_type + ".html").render(
        body=markeddown_text,
        meta={key: "".join(value) for (key, value) in md_template.Meta.items()},
    )
    replace_list = {
        "[swedac]": swedac_text,
        "[tick]": '<span class="icon_tick">&#10004;</span> ',
        "[cross]": '<span class="icon_cross">&#10008;</span> ',
        "[pass]": '<span class="pass">Pass</span>',
        "[fail]": '<span class="fail">Fail</span>',
        "[na]": "<code>NA</code>",
    }
    for key in replace_list:
        html_out = html_out.replace(key, replace_list[key])
    if not out_path:
        out_path = os.path.realpath(
            os.path.join(os.getcwd(), markdown_path.replace("md", "html"))
        )
    with open(out_path, "w") as f:
        f.write(html_out)
    return out_path


def main():
    parser = argparse.ArgumentParser("Make an NGI Report")
    parser.add_argument(
        "report_type",
        choices=allowed_report_types,
        metavar="<report type>",
        help="Type of report to generate. Choose from: {}".format(
            ", ".join(allowed_report_types)
        ),
    )
    parser.add_argument(
        "-d",
        "--dir",
        dest="working_dir",
        default=os.getcwd(),
        help="Working Directory. Default: cwd when script is executed.",
    )
    parser.add_argument(
        "-c",
        "--config_file",
        default=None,
        action="store",
        help="Configuration file to use instead of default (~/.ngi_config/ngi_reports.conf)",
    )
    parser.add_argument(
        "-p",
        "--project",
        default=None,
        action="store",
        help="Project name to generate 'project_summary' report",
    )
    parser.add_argument(
        "-s",
        "--signature",
        default=None,
        action="store",
        help="Signature/Name for person who generates 'project_summary' report",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default=None,
        action="store",
        type=int,
        help="Q30 threshold for samples to set status",
    )
    parser.add_argument(
        "-y",
        "--yield_from_fc",
        default=False,
        action="store_true",
        help="Compute the total for each sample from the retrived FC directly",
    )
    parser.add_argument(
        "--skip_fastq",
        action="store_true",
        help="Option to skip naming convention of fastq files from report",
    )
    parser.add_argument(
        "--exclude_fc",
        nargs="*",
        default=[],
        action="store",
        help="Exclude these FCs while processing, Format should be BH3JLWCCXX/000000000-AEUUP.",
    )
    parser.add_argument(
        "--no_txt",
        action="store_true",
        help="Use this option to not generate TXT files for tables",
    )
    parser.add_argument(
        "--samples",
        default=None,
        action="store",
        nargs="*",
        help="Limit the samples to include in reports",
    )
    parser.add_argument(
        "--samples_extra",
        default={},
        action="store",
        type=json.loads,
        help='Pass in extra information about samples as a json string, having each sample as a key. Example: --samples_extra \'{"TS001-1": {"delivered": "20150701"}}\'',
    )
    parser.add_argument(
        "--fc_phix",
        default={},
        action="store",
        type=json.loads,
        help='Overwrite or use Phix values for mentioned flowcells/lanes provided as a json string, having each flowcell as a key. Example: --fc_phix \'{"BH3JLWCCXX": {"1": "0.42", "3": "0.46"}}\'',
    )
    parser.add_argument(
        "--version",
        action="version",
        version="NGI reports version - {}".format(__version__),
    )
    parser.add_argument(
        "-md",
        "--markdown_file",
        default=None,
        help="Regenerate the html report from the given markdown file",
    )
    parser.add_argument(
        "-b",
        "--barcode_from_fc",
        default=False,
        action="store_true",
        help="retrieve the index from the FC directly (ONLY Illumina)",
    )

    kwargs = vars(parser.parse_args())

    if kwargs["markdown_file"]:
        print(
            "HTML report written to: "
            + markdown_to_html(
                kwargs["report_type"], markdown_path=kwargs["markdown_file"]
            )
        )
    else:
        make_reports(**kwargs)


# calling main method to generate report
if __name__ == "__main__":
    main()
