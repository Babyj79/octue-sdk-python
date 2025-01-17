FOLDER_DEFAULTS = {
    "configuration": "configuration",
    "input": "input",
    "tmp": "tmp",
    "output": "output",
}

VALUES_FILENAME = "values.json"
MANIFEST_FILENAME = "manifest.json"
CHILDREN_FILENAME = "children.json"

STRAND_FILENAME_MAP = {
    "configuration_values": VALUES_FILENAME,
    "configuration_manifest": MANIFEST_FILENAME,
    "input_values": VALUES_FILENAME,
    "input_manifest": MANIFEST_FILENAME,
    "output_values": VALUES_FILENAME,
    "output_manifest": MANIFEST_FILENAME,
}

# TODO this should probably be defined in twined
OUTPUT_STRANDS = ("output_values", "output_manifest")

# TODO this should probably be defined in twined
RUN_STRANDS = ("input_values", "input_manifest", "credentials", "children")
