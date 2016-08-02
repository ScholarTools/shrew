# -*- coding: utf-8 -*-
"""
Created on Sun Nov 15 14:35:23 2015

@author: RNEL
"""

class ParseException(Exception):
    pass

class InsufficientCredentialsException(Exception):
    pass

class InputError(Exception):
    pass

class ScraperError(Exception):
    pass

class UnsupportedPublisherError(Exception):
    pass

class UnsupportedEntryTypeError(Exception):
    pass

class InvalidConfig(Exception):
    pass

class OptionalLibraryError(Exception):
    pass


# ----------------- User Library Errors ----------------
class DOINotFoundError(KeyError):
    pass

class DocNotFoundError(KeyError):
    pass



class CallFailedException(Exception):
    pass

class PDFError(Exception):
    pass

class AuthException(Exception):
    pass


# ----------------- Database Errors --------------------
class MultipleDoiError(Exception):
    pass

class DatabaseError(Exception):
    pass
