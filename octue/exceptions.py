class OctueSDKException(Exception):
    """ All exceptions from this library inherit from here
    """


class InvalidInputException(OctueSDKException):
    """Raise when an object is instantiated or a function called with invalid inputs
    """


class FileNotFoundException(InvalidInputException, FileNotFoundError):
    """ Raise when a required folder (e.g. <data_dir>/input) cannot be found
    """


class FolderNotFoundException(InvalidInputException):
    """ Raise when a multi manifest can not be refined to a single manifest in a search
    """


class ManifestNotFoundException(InvalidInputException):
    """ Raise when a multi manifest can not be refined to a single manifest in a search
    """


class InvalidManifestException(InvalidInputException):
    """Raise when a manifest loaded from JSON does not pass validation
    """


class InvalidManifestTypeException(InvalidManifestException):
    """Raised when user attempts to create a manifest of a type other than 'input', 'output' or 'build'
    """


class InvalidOctueFileTypeException(OctueSDKException):
    """Raised when you attempt to register a file type in the results manifest that Octue doesn't know about
    """


class InvalidFilePointerException(OctueSDKException):
    """Raised when you attempt to create a Datafile with an object that is not file-like.
    """


class NotImplementedYetException(OctueSDKException):
    """Raised when you attempt to use a function whose high-level API is in place, but which is not implemented yet
    """


class UnexpectedNumberOfResultsException(OctueSDKException):
    """ Raise when searching for a single data file (or a particular number of data files) and the number of results
    exceeds that expected
    """


class InvalidTagException(OctueSDKException, ValueError):
    """ Raise when a tag applied to a data file or dataset
    """
