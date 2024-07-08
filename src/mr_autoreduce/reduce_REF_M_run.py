# standard imports
import os
import re
import shlex
import string
import sys
import tempfile
from pprint import pformat

# third party imports
from flask import Flask, abort, jsonify, render_template, request, send_from_directory

# mr_reduction imports
from mr_reduction.simple_utils import add_to_sys_path, namedtuplefy

TEMPLATED_AUTOREDUCTION_SCRIPT = os.path.join(os.path.dirname(__file__), "reduce_REF_M.py.template")
app = Flask(__name__)


def run_number(filepath):
    return re.search(r"REF_M_\d+", filepath).group(0)


@namedtuplefy
def reduce_single_run(opts):
    r"""
    Create a new "reduce_REF_M.py" script in a temporary directory and use it to reduce a single run

    Parameters
    ----------
    opts: dict
        Reduction options and paths to input Nexus events file and output directory

    Returns
    -------

    """
    # actualize the autoreduction template with `opts` and save in a temporary directory as reduce_REF_M.py
    with open(TEMPLATED_AUTOREDUCTION_SCRIPT, "r") as file_handle:
        template = string.Template(file_handle.read())
    script = template.substitute(**opts)
    with tempfile.TemporaryDirectory() as temp_dir:
        script_file = os.path.join(temp_dir, "reduce_REF_M.py")
        with open(script_file, "w") as file:
            file.write(script)
        os.system(f"/bin/cp {script_file} {opts['outdir']}")
        # import functions from newly created reduce_REF_M.py and reduce. Save HTML report and reduced files in outdir
        with add_to_sys_path(temp_dir):
            if "reduce_REF_M" in sys.modules:
                del sys.modules["reduce_REF_M"]  # need to re-import
            from reduce_REF_M import reduce_events_file, upload_html_report

            reports = reduce_events_file(opts["events_file"], opts["outdir"])
            report_file = os.path.join(opts["outdir"], f"REF_M_{run_number(opts['events_file'])}.html")
            upload_html_report(reports, publish=False, report_file=report_file)
    return {"report_file": report_file}


def wrong_options(opts):
    if os.path.isfile(opts["events_file"]) is False:
        return f"File {opts['events_file']} does not exist"
    if os.path.isdir(opts["outdir"]) is False:
        return f"Output directory {opts['outdir']} does not exist"
    return ""


@app.route("/")
def index():
    return render_template("reduction_options.html")


@app.route("/submit", methods=["POST"])
def submit():
    opts = request.json  # fetch reduction options as a dictionary
    print("REDUCTION OPTIONS:\n", pformat(opts))  # pretty print `opts`
    fails = wrong_options(opts)
    if fails:
        response = jsonify({"error": fails})
        response.status = 400
        return response
    output = reduce_single_run(opts)
    return jsonify({**opts, **{"report_file": output.report_file}})  # Return the JSON data as a response


@app.route("/report")
def show_file():
    report_file = request.args.get("report_file", None)
    if report_file is not None and os.path.isfile(report_file):
        parent_dir = os.path.dirname(report_file)
        file_name = os.path.basename(report_file)
        return send_from_directory(directory=parent_dir, path=file_name)
    else:
        abort(404, description="Report not found")


def main():
    command = "gunicorn --timeout 60 --bind :5000 reduce_REF_M_run:app"
    from gunicorn.app.wsgiapp import run

    sys.argv = shlex.split(command)
    run()
