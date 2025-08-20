import uuid
import json
import os

__root__ = os.path.split(__file__)[0]
__ENTITY_UUID = "$ENTITY_UUID"

def source_file_to_notebook_list(fn_in, str_replacement_dict):
    with open(os.path.join(__root__, fn_in), "r") as fid:
        lns = fid.readlines()
    
    clear_count = 0
    ret = []
    open_dict =  {
        'cell_type': 'code',
        'execution_count': None,
        'metadata': {},
        'outputs': [],
        'source': []
    }
    open_dict["id"] = uuid.uuid4().hex[:8]
    for ln in lns:
        for k, v in str_replacement_dict.items():
            ln = ln.replace(k, v)
        open_dict["source"].append(ln)
        if len(ln.strip()) == 0:
            clear_count += 1
        else:
            clear_count = 0
        if clear_count >= 2:
            clear_count = 0
            ret.append(open_dict)
            open_dict =  {
                'cell_type': 'code',
                'execution_count': None,
                'metadata': {},
                'outputs': [],
                'source': []
            }
            open_dict["id"] = uuid.uuid4().hex[:8]
    ret.append(open_dict)
    return ret


def inject_selection_widget(fn_in, fn_out, entity_type, variable_name):
    with open(fn_in, "r") as fid:
        nb = json.load(fid)
    
    if entity_type == "circuit":
        str_replacements = {"$CIRC": variable_name}
        nb["cells"] = source_file_to_notebook_list("./_inject_circuit_selector.py",
                                                   str_replacement_dict=str_replacements) +\
                                                   nb["cells"]
    nb["cells"] = source_file_to_notebook_list("./_inject_project_selector.py", {}) +\
                  nb["cells"]

    with open(fn_out, "w") as fid:
        json.dump(nb, fid, indent=4)


def inject_selected_ids(fn_in, fn_out, entity_type, entity_uuid, variable_name):
    with open(fn_in, "r") as fid:
        nb = json.load(fid)
    
    if entity_type == "circuit":
        str_replacements = {"$CIRC": variable_name, __ENTITY_UUID: f"'{entity_uuid}'"}
        nb["cells"] = source_file_to_notebook_list("./_inject_selected_circuit.py",
                                                   str_replacement_dict=str_replacements) +\
                                                   nb["cells"]
    nb["cells"] = source_file_to_notebook_list("./_inject_project_selector.py", {}) +\
                  nb["cells"]

    with open(fn_out, "w") as fid:
        json.dump(nb, fid, indent=4)
