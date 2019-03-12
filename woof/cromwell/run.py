"""Run Cromwell with config, input and options"""

import os
import sys
import json
from woof import utils
from woof.cromwell import configs

def create_cromwell_files(dname, project):
    """
    Writes following to given dname:
    1. config
    2. options
    3. inputs.json
    4. WDL files
    """
    work_dir = utils.safe_mkdir(os.path.join(dname, "woof", "work"))
    final_dir = utils.safe_mkdir(os.path.join(dname, "woof", "final"))

    config_hocon = create_cromwell_config(work_dir)
    config_file = os.path.join(work_dir, f"{project}-cromwell.conf")
    with open(config_file, "w") as out_handle:
        out_handle.write(config_hocon)

    opts = configs.OPTIONS
    opts["final_workflow_outputs_dir"] = final_dir
    option_file = os.path.join(work_dir, f"{project}-cromwell_opts.json")
    with open(option_file, "w") as out_handle:
        json.dump(opts, out_handle)

    log_file = os.path.join(work_dir, f"{project}-cromwell.log")
    metadata_file = os.path.join(work_dir, f"{project}-cromwell_meta.json")


    res = {
        "config_file": config_file,
        "option_file": option_file,
        "log_file": log_file,
        "metadata_file": metadata_file,
        }

    return res


def create_cromwell_config(dname):
    """Prepare a cromwell configuration within the specified directory.
    """
    joblimit = 1
    filesystem = utils.get_filesystem() # SPARTAN/RAIJIN/AWS/OTHER - dealing with single fs for now
    file_types = set(["s3" if filesystem == "AWS" else "local"])
    std_args = {"docker_attrs": "",
                "submit_docker": 'submit-docker: ""',
                "joblimit": "concurrent-job-limit = %s" % (joblimit) if joblimit > 0 else "",
                "filesystem": _get_filesystem_config(file_types),
                "database": configs.DATABASE_CONFIG % {"dname": dname}}
    conf_args = {}
    std_args["engine"] = _get_engine_filesystem_config(file_types)
    conf_args.update(std_args)
    scheduler = None
    cloud_type = None
    main_config = {"hpc": (configs.HPC_CONFIGS[scheduler] % conf_args) if scheduler else "",
                   "cloud": (configs.CLOUD_CONFIGS[cloud_type] % conf_args) if cloud_type else "",
                   "work_dir": dname}
    main_config.update(std_args)

    return configs.CROMWELL_CONFIG % main_config

def _get_filesystem_config(file_types):
    """Retrieve filesystem configuration, including support for specified file types.
    """
    out = "     filesystems {\n"
    for file_type in sorted(list(file_types)):
        if file_type in configs.FILESYSTEM_CONFIG:
            out += configs.FILESYSTEM_CONFIG[file_type]
    out += "      }\n"
    return out

def _get_engine_filesystem_config(file_types):
    """Retriever authorization and engine filesystem configuration.
    """
    file_types = [x for x in list(file_types)]
    out = ""
    if "s3" in file_types:
        region = "ap-southeast-2"
        out += configs.AUTH_CONFIG_AWS % region
        out += "engine {\n"
        out += "  filesystems {\n"
        out += '    s3 { auth = "default" }'
        out += "  }\n"
        out += "}\n"

    return out



def run_cromwell(args):
    """Run Cromwell

    cromwell run \
            --inputs <input.json> \
            --Dconfig=<config.conf> \
            --DLOG_LEVEL=<ERROR|WARN|INFO> \
            --options <options.json> \
            --metadata-output <meta.json> \
            workflow.wdl
    """

    # The only things that change depending on project are inputs and workflow.
    # So the command should take those two as args.
    wdl_workflow, input_json, project_name = _get_main_and_json(args.directory)

    cmd = ["cromwell", "-Xms1g", "-Xmx3g", "run", "--type", "CWL",
           "-Dconfig.file=%s" % hpc.create_cromwell_config(args, work_dir, json_file)]
    cmd += hpc.args_to_cromwell_cl(args)
    cmd += ["--metadata-output", metadata_file, "--options", option_file,
            "--inputs", json_file, main_file]
    with utils.chdir(work_dir):
        _run_tool(cmd, not args.no_container, work_dir, log_file)
        if metadata_file and utils.file_exists(metadata_file):
            with open(metadata_file) as in_handle:
                metadata = json.load(in_handle)
            if metadata["status"] == "Failed":
                _cromwell_debug(metadata)
                sys.exit(1)
            else:
                _cromwell_move_outputs(metadata, final_dir)
