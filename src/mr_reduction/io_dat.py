"""Read QuickNXS reduced data files (.dat) in a legacy-compatible format."""

import copy
import inspect
import logging
import os
from pathlib import Path
from typing import Any, Optional

from mr_reduction.beam_options import DirectBeamOptions, ReflectedBeamOptions

CONFIG_LABELS = {
    "scaling_factor": "scale",
    "scaling_error": "scale_err",
    "cut_first_n_points": "P0",
    "cut_last_n_points": "PN",
    "peak_position": "x_pos",
    "peak_width": "x_width",
    "low_res_position": "y_pos",
    "low_res_width": "y_width",
    "bck_position": "bg_pos",
    "bck_width": "bg_width",
    "binning_type_global": "g_final_rebin",
    "binning_q_step_global": "g_Qsteps",
    "binning_type_run": "r_final_rebin",
    "binning_q_step_run": "r_Qsteps",
    "tof_bins": "bin_width",
    "total_reflectivity_q_cutoff": "critical_q_cutoff",
    "direct_pixel_overwrite": "dpix",
    "use_metadata_bck_roi": "force_bck_roi",
}

LABEL_TO_CONFIG = {value: key for key, value in CONFIG_LABELS.items()}


def _find_h5_data(filename: str) -> str:
    """Get the corresponding .nxs.h5 file path for a legacy .nxs path when available."""
    if filename.endswith(".nxs"):
        new_filename = filename.replace("_histo.nxs", ".nxs.h5")
        new_filename = new_filename.replace("_event.nxs", ".nxs.h5")
        new_filename = new_filename.replace("data", "nexus")
        if os.path.isfile(new_filename):
            logging.warning("Using %s", new_filename)
            return new_filename
    return filename


def _get_tok(col_name: str, cols: list[str], toks: list[str]) -> Optional[str]:
    """Get token value by column name."""
    try:
        return toks[cols.index(col_name)]
    except ValueError:
        return None


def _parse_value(value_str: str) -> Any:
    """Best-effort parse of string token values into Python primitives."""
    value_str = value_str.strip()
    lower = value_str.lower()
    if lower in ("true", "false"):
        return lower == "true"
    if value_str == "None":
        return None
    if "[" in value_str and "]" in value_str:
        stripped = value_str.replace("[", "").replace("]", "")
        if stripped == "":
            return []
        return [float(item) for item in stripped.split(",") if item.strip()]
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        return value_str


def _assign_config_value(conf: object, attr: str, value_str: str):
    """Assign a string value to a configuration-like object with type inference."""
    if not hasattr(conf, attr):
        return

    value_str = value_str.strip()
    try:
        current_value = getattr(conf, attr)
        if isinstance(current_value, bool):
            value = value_str.lower() in ("true", "1", "yes")
        elif isinstance(current_value, float):
            value = float(value_str)
        elif isinstance(current_value, int):
            try:
                value = int(value_str)
            except ValueError:
                value = float(value_str)
        elif value_str == "None":
            value = None
        elif isinstance(current_value, list) or ("[" in value_str and "]" in value_str):
            value_str = value_str.replace("[", "").replace("]", "")
            if value_str == "":
                value = []
            else:
                value = [float(item) for item in value_str.split(",") if item.strip()]
        else:
            value = value_str
        setattr(conf, attr, value)
    except (AttributeError, ValueError, TypeError) as error:
        logging.error("Failed to assign config value: %s = %s -> %s", attr, value_str, error)


def determine_which_files_to_sum(run_file: str, data_file_indices: str, run_number_str: str = None) -> str:
    """Determine which file paths are summed for a data run entry."""
    if run_number_str and "+" in run_number_str:
        run_numbers = run_number_str.split("+")
        output = ""
        for run_num in run_numbers:
            if output:
                output += "+"
            file_with_new_run = run_file
            for old_run in run_numbers:
                if old_run in run_file:
                    file_with_new_run = run_file.replace(old_run, run_num)
                    break
            output += file_with_new_run
        return output

    if not data_file_indices:
        return run_file

    indices_str = str.split(data_file_indices)[-1]
    if "," in indices_str:
        runs = str.split(indices_str, ",")
    elif "+" in indices_str:
        runs = str.split(indices_str, "+")
    else:
        runs = [indices_str]

    output = run_file
    for run in runs:
        numors = str.split(run, ":")
        if len(numors) > 1 and (str.split(run, ":")[0] in run_file):
            output = ""
            for run_number in range(int(numors[0]), int(numors[-1]) + 1):
                output = output + "+" + run_file.replace(numors[0], str(run_number))
            output = output[1:]
        if len(numors) == 1 and (str.split(run, ":")[0] in run_file):
            output = run_file

    return output


def read_reduced_file(file_path: str, configuration=None):
    """Read reduced-file entries using a QuickNXS legacy-compatible return signature."""
    direct_beam_runs = []
    data_runs = []
    additional_peaks = []
    config_properties = []
    if configuration is not None:
        config_properties = [
            name for name, _ in inspect.getmembers(type(configuration), lambda item: isinstance(item, property))
        ]

    with open(file_path, "r") as file_content:
        in_section = 0
        file_start = True
        has_scaling_error = False
        db_id_is_zero_based = None
        data_file_indices = ""
        peak_index = 0
        for line in file_content.readlines():
            if file_start and not (
                line.startswith("# Datafile created by QuickNXS")
                or line.startswith("# Datafile created by mr_reduction QuickNXS")
            ):
                raise RuntimeError("The selected file does not conform to the QuickNXS format")
            file_start = False
            if "Input file indices" in line:
                data_file_indices = line

            if "[Direct Beam Runs]" in line:
                in_section = 1
            elif "[Data Runs]" in line:
                in_section = 2
            elif "[Peak 1 Runs]" in line:
                in_section = 2
                data_runs = []
            elif "[Peak" in line:
                in_section = 3
                peak_index = int(line.split("[Peak ")[1].split(" Runs]")[0])
            elif "[Global Options]" in line:
                in_section = 4
            elif "[Data]" in line:
                in_section = 0
                continue

            if in_section == 1:
                toks = line.replace(", ", ",").split()
                if "DB_ID" in toks:
                    cols = toks
                    continue
                if len(toks) < 14:
                    continue
                try:
                    if db_id_is_zero_based is None:
                        first_db_id = int(_get_tok("DB_ID", cols, toks))
                        db_id_is_zero_based = first_db_id == 0

                    if configuration is not None:
                        conf = copy.deepcopy(configuration)
                        for label in cols:
                            attr = LABEL_TO_CONFIG.get(label, label)
                            value_str = _get_tok(label, cols, toks)
                            if value_str is not None and attr not in config_properties:
                                _assign_config_value(conf, attr, value_str)
                        row_payload = conf
                    else:
                        row_payload = {
                            label: _parse_value(_get_tok(label, cols, toks)) for label in cols if label != "#"
                        }

                    run_number_str = str(_get_tok("number", cols, toks))
                    if "+" in run_number_str:
                        run_number = int(run_number_str.split("+")[0])
                    else:
                        run_number = int(run_number_str)
                    slice_str = _get_tok("slice", cols, toks)
                    slice_value = int(slice_str) if slice_str is not None else 0
                    run_file = str(_get_tok("File", cols, toks))
                    if not Path(run_file).is_absolute():
                        run_file = str(Path(file_path).parent / run_file)
                    if run_file.endswith("histo.nxs"):
                        run_file = run_file.replace("histo.", "event.")
                    run_file = _find_h5_data(run_file)
                    direct_beam_runs.append([run_number, run_file, row_payload, slice_value])
                except ValueError:
                    logging.error("Unable to parse line '%s' in run file %s", line, run_file)

            if in_section in (2, 3):
                toks = line.replace(", ", ",").split()
                if "DB_ID" in toks:
                    cols = toks
                    continue
                if len(toks) < 16:
                    continue
                try:
                    if configuration is not None:
                        conf = copy.deepcopy(configuration)
                        for label in cols:
                            attr = LABEL_TO_CONFIG.get(label, label)
                            value_str = _get_tok(label, cols, toks)
                            if value_str is not None and attr not in config_properties:
                                _assign_config_value(conf, attr, value_str)
                                if label == "scale_err":
                                    has_scaling_error = True
                        db_id = int(_get_tok("DB_ID", cols, toks))
                        if db_id_is_zero_based:
                            if db_id >= 0 and len(direct_beam_runs) > db_id:
                                conf.direct_beam = direct_beam_runs[db_id][0]
                        else:
                            if db_id > 0 and len(direct_beam_runs) >= db_id:
                                conf.direct_beam = direct_beam_runs[db_id - 1][0]
                        row_payload = conf
                    else:
                        row_payload = {
                            label: _parse_value(_get_tok(label, cols, toks)) for label in cols if label != "#"
                        }
                        has_scaling_error = has_scaling_error or ("scale_err" in row_payload)

                    run_number_str = str(_get_tok("number", cols, toks))
                    if "+" in run_number_str:
                        run_number = int(run_number_str.split("+")[0])
                    else:
                        run_number = int(run_number_str)
                    slice_str = _get_tok("slice", cols, toks)
                    slice_value = int(slice_str) if slice_str is not None else 0
                    run_file = str(_get_tok("File", cols, toks))
                    if not Path(run_file).is_absolute():
                        run_file = str(Path(file_path).parent / run_file)
                    if run_file.endswith("histo.nxs"):
                        run_file = run_file.replace("histo.", "event.")
                    run_file = _find_h5_data(run_file)
                    run_file = determine_which_files_to_sum(run_file, data_file_indices, run_number_str)

                    if in_section == 2:
                        data_runs.append([run_number, run_file, row_payload, slice_value])
                    else:
                        additional_peaks.append([peak_index, run_number, run_file, row_payload, slice_value])
                except ValueError:
                    logging.error("Unable to parse line '%s' in run file %s", line, run_file)

            if in_section == 4 and line.startswith("# "):
                try:
                    label, value = line[2:].strip().split(" ", 1)
                except ValueError:
                    continue
                if configuration is not None:
                    attr = LABEL_TO_CONFIG.get(label, label)
                    _assign_config_value(type(configuration), attr, value)

    return direct_beam_runs, data_runs, additional_peaks, has_scaling_error


def _row_to_direct_beam_options(row_data: dict[str, Any]) -> DirectBeamOptions:
    """Create DirectBeamOptions from a parsed reduced-file row."""
    return DirectBeamOptions(
        DB_ID=int(row_data["DB_ID"]),
        P0=int(row_data["P0"]),
        PN=int(row_data["PN"]),
        x_pos=float(row_data["x_pos"]),
        x_width=float(row_data["x_width"]),
        y_pos=float(row_data["y_pos"]),
        y_width=float(row_data["y_width"]),
        bg_pos=float(row_data["bg_pos"]),
        bg_width=float(row_data["bg_width"]),
        dpix=float(row_data["dpix"]),
        tth=float(row_data["tth"]),
        number=int(row_data["number"]),
        File=str(row_data["File"]),
    )


def _row_to_reflected_beam_options(row_data: dict[str, Any]) -> ReflectedBeamOptions:
    """Create ReflectedBeamOptions from a parsed reduced-file row."""
    fan = row_data["fan"]
    if isinstance(fan, str):
        fan = fan.lower() == "true"

    return ReflectedBeamOptions(
        scale=float(row_data["scale"]),
        P0=int(row_data["P0"]),
        PN=int(row_data["PN"]),
        x_pos=float(row_data["x_pos"]),
        x_width=float(row_data["x_width"]),
        y_pos=float(row_data["y_pos"]),
        y_width=float(row_data["y_width"]),
        bg_pos=float(row_data["bg_pos"]),
        bg_width=float(row_data["bg_width"]),
        fan=bool(fan),
        dpix=float(row_data["dpix"]),
        tth=float(row_data["tth"]),
        number=str(row_data["number"]),
        DB_ID=int(row_data["DB_ID"]),
        File=str(row_data["File"]),
    )


def read_reduced_file_options(
    file_path: str,
) -> tuple[list[DirectBeamOptions], list[ReflectedBeamOptions], list[tuple[int, ReflectedBeamOptions]], bool]:
    """Read reduced-file options as mr_reduction beam option objects.

    Returns
    -------
    tuple
        direct_beam_options, data_run_options, additional_peak_options, has_scaling_error
    """
    direct_beam_runs, data_runs, additional_peaks, has_scaling_error = read_reduced_file(file_path)

    direct_beam_options = []
    for _, _, row_payload, _ in direct_beam_runs:
        if not isinstance(row_payload, dict):
            raise TypeError("Expected dict payload for direct beam row when reading reduced-file options")
        direct_beam_options.append(_row_to_direct_beam_options(row_payload))

    data_run_options = []
    for _, _, row_payload, _ in data_runs:
        if not isinstance(row_payload, dict):
            raise TypeError("Expected dict payload for data run row when reading reduced-file options")
        data_run_options.append(_row_to_reflected_beam_options(row_payload))

    additional_peak_options = []
    for peak_index, _, _, row_payload, _ in additional_peaks:
        if not isinstance(row_payload, dict):
            raise TypeError("Expected dict payload for additional peak row when reading reduced-file options")
        additional_peak_options.append((int(peak_index), _row_to_reflected_beam_options(row_payload)))

    return direct_beam_options, data_run_options, additional_peak_options, has_scaling_error


def read_reduced_file_metadata(file_path: str) -> dict[str, Any]:
    """Extract commonly used header metadata from a reduced file."""
    metadata = {
        "input_file_indices": None,
        "extracted_states": None,
        "sequence_id": None,
        "lowest_q": None,
    }
    with open(file_path, "r") as file_handle:
        for line in file_handle:
            if line.startswith("# Input file indices:"):
                metadata["input_file_indices"] = line[len("# Input file indices:") :].strip()
            elif line.startswith("# Extracted states:"):
                metadata["extracted_states"] = line[len("# Extracted states:") :].strip()
            elif line.startswith("# sequence_id"):
                try:
                    metadata["sequence_id"] = int(line[len("# sequence_id") :].strip())
                except ValueError:
                    logging.error("Could not extract sequence_id from line: %s", line.strip())
            elif metadata["lowest_q"] is None and (not line.startswith("#")) and line.strip():
                try:
                    metadata["lowest_q"] = float(line.split()[0])
                except (ValueError, IndexError):
                    logging.error("Could not extract lowest q from line: %s", line.strip())
            if (
                all(metadata[key] is not None for key in ("input_file_indices", "sequence_id", "lowest_q"))
                and metadata["extracted_states"] is not None
            ):
                break
    return metadata
