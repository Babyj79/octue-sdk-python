import os


def isfolder(*args):
    """Returns true if input path is the name of a valid, existing, file. Joins multiple inputs.

    tf = isfolder(str) Returns true is str is a full (or relative from the current working directory) folder path, false otherwise.

    tf = isfolder(str1, str2, ...) Concatenates any number of strings using the platform-specific file separator before testing for presence of the folder. Equivalent to typing octue.utils.isfolder(os.path.join(str1, str2, ...))
    """
    return os.path.isfile(os.path.join(*args))
