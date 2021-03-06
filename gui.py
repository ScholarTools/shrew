# Standard
import sys
import os
import inspect
import subprocess

# Third-party
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# Local imports
from mendeley import client_library
from mendeley.api import API
from mendeley import db_interface as db


import reference_resolver as rr
from shrew_utils import get_truncated_display_string as td
import error_logging

# I'd like to only have shrew_errors, but then the
# errors that come up are from other repos. Even though
# they have the same name, they're not being caught because
# they're from different locations.
# from shrew_errors import *
from mendeley.errors import *
from pypub.pypub_errors import *
from pdfetch.pdfetch_errors import *


class EntryWindow(QWidget):
    """
    This is the main window of the application.

    --- Overview of Usage ---
    User inputs a DOI. The indicator button to the left of the text box will
    turn green if the DOI within the text field is in the user's library.
    From there, the user can get the references for the paper, which will appear
    in a large box below the buttons, or the user can open up the notes editor,
    which appears in a smaller, new window. The notes can be edited and saved.

    --- Features ---
    * Indicator button next to the text field turns green if the entered DOI
       is found in the user's library. This is done automatically.
    * Get References button creates a list of the references for the paper
       entered in the text box. See "ReferenceLabel" for more information.
    * Open Notes button opens a new window with the Mendeley notes about
       the paper. These can be edited and saved.

    TODOs:
     - Implement URL input capability, not just DOI
     - Implement reading the abstract of any paper

    """
    def __init__(self, parent_tab_window=None, encapsulating_window=None):
        super(EntryWindow, self).__init__()

        self.library = LibraryInterface.create('Mendeley')

        self.fModel = FunctionModel(self)
        self.data = Data()

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.parent_tab_window=parent_tab_window
        self.encapsulating_window = encapsulating_window

        self.initUI()

    def initUI(self):

        # Make all widgets
        self.entryLabel = QLabel('Please enter information')
        self.indicator = QPushButton()
        self.textEntry = QLineEdit()
        self.doi_check = QRadioButton('DOI')
        self.doi_check.setChecked(True)
        self.url_check = QRadioButton('URL')
        self.fulltext_check = QRadioButton('Full Text')
        self.pmid_check = QRadioButton('PMID')
        self.refresh = QPushButton('Sync with Library')
        self.get_references = QPushButton('Get References')
        self.open_notes = QPushButton('Open Notes')
        self.add_to_lib = QPushButton('Add to Library')
        self.trash = QPushButton('Move to Trash')
        self.forward_refs = QPushButton('Follow Refs Forward')
        self.manual_entry = QPushButton('Enter References')
        self.history = QComboBox()
        self.response_label = QLabel()
        self.ref_area = QScrollArea()
        self.get_all_refs = QPushButton('Add All References')
        self.resolve_dois = QPushButton('Resolve DOIs to References')

        # Set connections to functions
        self.textEntry.textChanged.connect(self.text_changed)
        self.textEntry.returnPressed.connect(self.get_refs)
        self.get_references.clicked.connect(self.get_refs)
        self.open_notes.clicked.connect(self.show_main_notes_box)
        self.add_to_lib.clicked.connect(self.add_to_library_from_main)
        self.get_all_refs.clicked.connect(self.add_all_refs)
        self.resolve_dois.clicked.connect(self.get_all_dois)
        self.refresh.clicked.connect(self.fModel.resync)
        self.trash.clicked.connect(self.move_to_trash)
        self.forward_refs.clicked.connect(self.follow_refs_forward)
        self.manual_entry.clicked.connect(self.ref_entry)

        # Disable the radio buttons with options that aren't supported
        self.url_check.setDisabled(True)
        self.fulltext_check.setDisabled(True)
        self.pmid_check.setDisabled(True)

        # Make scroll items widget
        self.ref_items = QWidget()
        items_layout = QVBoxLayout()
        items_layout.addStretch(1)
        self.ref_items.setLayout(items_layout)
        self.ref_items_layout = self.ref_items.layout()

        # Format scrollable reference area
        self.ref_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.ref_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ref_area.setWidgetResizable(True)
        ref_layout = QVBoxLayout()
        self.ref_area.setLayout(ref_layout)
        self.ref_area_layout = self.ref_area.layout()
        self.ref_area.setWidget(self.ref_items)
        self.ref_area.hide()

        # Create a horizontal box to be added to vbox later
        # The radiobuttons having the same parent widget ensures
        # that they are part of a group and only one can be checked.
        checkboxes = QHBoxLayout()
        checkboxes.addWidget(self.doi_check)
        checkboxes.addWidget(self.url_check)
        checkboxes.addWidget(self.fulltext_check)
        checkboxes.addWidget(self.pmid_check)
        checkboxes.addWidget(self.refresh)
        checkboxes.addWidget(self.get_references)
        checkboxes.addWidget(self.open_notes)
        checkboxes.addStretch(1)

        # Another horizontal box
        line2 = QHBoxLayout()
        line2.addWidget(self.add_to_lib)
        line2.addWidget(self.trash)
        line2.addWidget(self.forward_refs)
        line2.addWidget(self.history)
        line2.addWidget(self.manual_entry)
        line2.addStretch(1)

        # Yet another horizontal box
        bottomline = QHBoxLayout()
        bottomline.addWidget(self.get_all_refs)
        bottomline.addWidget(self.resolve_dois)

        # Create a vertical box layout.
        # Populate with widgets and add stretch space at the bottom.
        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.entryLabel)

        # Create a horizontal box for indicator and textEntry
        self.doc_selector = DocSelector(window=self)
        ds_view = self.doc_selector.text_view
        textline = ds_view.create_text_layout(textEntry=self.textEntry, indicator=self.indicator)
        self.vbox.addLayout(textline)

        self.vbox.addLayout(checkboxes)
        self.vbox.addLayout(line2)
        self.vbox.addWidget(self.response_label)
        self.vbox.addWidget(self.ref_area)
        self.vbox.addLayout(bottomline)
        self.vbox.addStretch(1)

        self.response_label.hide()

        # Set layout to be the vertical box.
        self.setLayout(self.vbox)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(lambda: _copy_to_clipboard(self.textEntry.textCursor().selectedText()))


    # +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+= Start of Functions

    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Main Window Button Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def text_changed(self):
        doc_id = self.doc_selector.value
        self.update_document_status(doi=doc_id, adding=False, sync=False, popups=False)

    def get_refs(self):
        """
        Gets references for paper corresponding to the DOI in text field.
        Displays reference information in scrollable area.
        """
        self.response_label.hide()

        # Get DOI from text field and handle blank entry
        entered_doi = self.doc_selector.value

        if entered_doi == '':
            self._set_response_message('Please enter text above.')
            return

        # Resolve DOI and get references
        refs = self.fModel.retrieve_only_refs(doi=entered_doi)

        if refs is None or len(refs) == 0:
            self.data.references = None
            _send_msg('No references found.')
            return

        # First clean up existing GUI window.
        # If there are widgets in the layout (i.e. from the last call to 'get_refs'),
        # delete all of those reference labels before adding more.
        _delete_all_widgets(self.ref_items_layout)

        for ref in refs:
            ref_label = self.ref_to_label(ref)
            self.ref_items_layout.insertWidget(self.ref_area_layout.count() - 1, ref_label)

        # Add entry to history
        self.doc_selector.add_to_history(entered_doi)

        self.response_label.hide()
        self.ref_area.show()

    #
    # For "Open Notes", see "Notes Box Display Functions" section below.
    #

    def add_to_library_from_main(self):
        """
        Adds paper corresponding to the DOI in the text field to the user library,
        if it is not already there.
        """
        if self.doc_selector.status in (1,2):
            _send_msg('Paper is already in library.')
            return

        doi = self.doc_selector.value
        if doi is None or doi == '':
            self._set_response_message('Please enter text above.')
            return

        try:
            self.library.add_to_library(doi)
        except UnsupportedPublisherError as exc:
            error_logging.log(method='gui.Window.add_to_library_from_main', message='Unsupported publisher', error=str(exc), doi=doi)
            _send_msg('Publisher is not yet supported.\nDocument not added.')
            return
        except CallFailedException as call:
            error_logging.log(method='gui.Window.add_to_library_from_main', message='Call failed', error=str(call), doi=doi)
            _send_msg(str(call))
        except ParseException or AttributeError as exc:
            error_logging.log(method='gui.Window.add_to_library_from_main', message='Error while parsing article webpage',
                error=str(exc), doi=doi)
            _send_msg('Error while parsing article webpage.')
        except PDFError:
            _send_msg('PDF could not be retrieved.')
        except Exception as exc:
            error_logging.log(method='gui.Window.add_to_library_from_main', error=str(exc), doi=doi)
            _send_msg(str(exc))

        # Add entry to history
        self.doc_selector.add_to_history(doi)

        self.update_document_status(doi, adding=True)

    def move_to_trash(self, doi=None):
        """
        Moves a paper from the user's library to trash
        (in Mendeley).

        Parameters
        ----------
        doi : str
            DOI of the paper to be deleted.
        """

        # This method can be called with doi as None or
        # as False (which is default if connected from
        # a GUI button) so this looks for String DOIs
        if isinstance(doi, str):
            entry_type = 'doi'
            value = doi
        else:
            entry_type = self.doc_selector.entry_type
            value = self.doc_selector.value

        try:
            self.library.trash_document(**{entry_type: value})
        except DocNotFoundError:
            _send_msg('Document not found in library.')
            return
        except UnsupportedEntryTypeError:
            _send_msg('Only functions using DOIs are supported at this time.')
            return

        # Add entry to history
        self.doc_selector.add_to_history(value)

        self.update_document_status(doi=value)

    def follow_refs_forward(self):
        doi = self.doc_selector.value
        things = db.follow_refs_forward(doi)

        # First clean up existing GUI window.
        # If there are widgets in the layout (i.e. from the last call to 'get_refs'),
        # delete all of those reference labels before adding more.
        _delete_all_widgets(self.ref_items_layout)

        for thing in things:
            ref_label = self.ref_to_label(thing)
            self.ref_items_layout.insertWidget(self.ref_area_layout.count() - 1, ref_label)

        # Add entry to history
        self.doc_selector.add_to_history(doi)

        self._set_response_message('Papers in your database that cite the given DOI.\n'
                                   'List may not be exhaustive.')

        # self.response_label.hide()
        self.ref_area.show()

    def ref_entry(self):
        """
        This function is for manual reference entry. It creates a pop-up window in which
        a user may enter the information for each reference by hand.
        If there is a file found in their library for the document, the user has the option
        to open it up for reference.

        """
        if self.doc_selector.entry_type == 'doi':
            doi = self.doc_selector.value
        elif self.data.doi is not None:
            doi = self.data.doi
        else:
            _send_msg('Reference entry requires a DOI.')
            return

        if self.data.doc_response_json is not None:
            doc = self.data.doc_response_json
        else:
            doc = self.library.get_document(doi=doi, return_json=True)
        doc_id = doc.get('id')

        # If there is a file attached to the user's document, offer the option to open the file.
        if self.doc_selector.status == 2:
            reply = QMessageBox.question(self, 'Message', 'A file has been found for this document.\n'
                  'Would you like to open it for reference?', QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

            if reply == QMessageBox.Yes:
                # Get the content and name of the attached pdf
                try:
                    file_content, _, file_id = self.library.get_file_content_from_doc_id(doc_id=doc_id)
                except Exception as exc:
                    _send_msg('File retrieval from Mendeley failed.')
                    return

                # Get the directory of the current running script to use for temp storage
                package_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
                temp_filename = os.path.join(package_path, 'temp.pdf')

                # Write contents of pdf from user library to a temporary file.
                with open(temp_filename, 'wb') as temp_file:
                    temp_file.write(file_content)

                # Open the temp file for viewing
                _open_file(filename=temp_filename)

        ref_window = ReferenceEntryWindow(main_paper_doi=doi, library=self.library)
        ref_window.show()

    def add_all_refs(self):
        """
        Attempts to add every reference from the paper corresponding
        to the DOI in the text field to the user's library.
        """
        # The ref_items_layout would hold the ref_labels.
        # If count is 0, none are listed, and it needs to be populated.
        if self.ref_items_layout.count() == 1:
            self.get_refs()

        main_doi = self.doc_selector.value
        self.response_label.show()

        self.fModel.add_all_refs(main_doi=main_doi, ref_labels=self.ref_items_layout)

        self.response_label.hide()

    def get_all_dois(self):
        """
        Attempts to retrieve DOIs corresponding to each reference.
        """
        # The ref_items_layout would hold the ref_labels.
        # If count is 0, none are listed, and it needs to be populated.
        if self.ref_items_layout.count() == 1:
            self.get_refs()

        self.response_label.show()

        citing_doi = self.doc_selector.value

        for x in range(1, self.ref_items_layout.count()):
            label = self.ref_items_layout.itemAt(x).widget()

            if label.doi is not None:
                continue

            self.response_label.setText('Finding DOI for: ' + label.small_text)
            self.response_label.repaint()
            qApp.processEvents()

            authors = label.reference.get('authors')
            date = label.reference.get('year')
            if date is None:
                date = label.reference.get('date')

            lookup = label.expanded_text
            lookup = lookup.replace('\n', ' ')
            doi, retrieved_title = rr.doi_and_title_from_citation(lookup)
            if doi is not None and '10.' in doi:
                label.doi = doi
                title = label.reference.get('title')

                # This is if there is no title in a given reference
                if title is None:
                    title = retrieved_title
                    label.reference.title = title
                    if title is not None:
                        if len(title) > 60:
                            short_title = title[0:60]
                        else:
                            short_title = title
                        label.small_text = label.small_text + short_title
                        label.expanded_text = label.expanded_text + '\n' + title

                label.expanded_text = label.expanded_text + '\n' + doi

                # TODO: move database interaction out of the window class
                if authors is not None:
                    # Update the reference entry within the database to
                    # reflect the change.
                    db.update_reference_field(identifying_value=date, updating_field=['doi', 'title'],
                                            updating_value=[doi, title], citing_doi=citing_doi,
                                            authors=authors, filter_by_authors=True)
                elif title is not None:
                    # Update the reference entry within the database to
                    # reflect the change.
                    db.update_reference_field(identifying_value=title, updating_field=['doi', 'title'],
                                        updating_value=[doi, title], filter_by_title=True)
            label.update_status(doi=doi, popups=False, sync=False)

        self.response_label.hide()
        self.library.sync()


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Reference Label Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def ref_to_label(self, ref):
        """
        Creates a ReferenceLabel object from a single paper reference.
        Formats title, author information for display, connects functionality
        to the label object.
        Used by get_refs().

        Parameters
        ----------
        ref: dict
            Contains information from a single paper reference.

        Returns
        -------
        ref_label: ReferenceLabel
            For display in reference box.
        """
        # Extract main display info
        ref_id = ref.get('ref_id')
        ref_title = ref.get('title')
        ref_author_list = ref.get('authors')
        ref_doi = ref.get('doi')
        ref_year = ref.get('year')
        if ref_year is None:
            ref_year = ref.get('date')

        if isinstance(ref_author_list, str):
            ref_author_list = ref_author_list.split('; ')

        # Format short and long author lists
        if ref_author_list is not None:
            ref_full_authors = '; '.join(ref_author_list)
            if len(ref_author_list) > 2:
                ref_first_authors = ref_author_list[0] + ', ' + ref_author_list[1] + ', et al.'
            else:
                ref_first_authors = ref_full_authors
        else:
            ref_first_authors = ''
            ref_full_authors = ''

        # Initialize indicator about whether reference is in library
        in_lib = 3

        # Build up strings with existing info
        # Small text is for abbreviated preview.
        # Expanded text is additional information for the larger
        # reference view when a label is clicked.
        ref_small_text = ''
        ref_expanded_text = ''
        if ref_id is not None:
            ref_small_text = ref_small_text + str(ref_id) + '. '
            ref_expanded_text = ref_expanded_text + str(ref_id) + '. '
        if ref_author_list is not None:
            ref_small_text = ref_small_text + ref_first_authors
            ref_expanded_text = ref_expanded_text + ref_full_authors
        if ref.get('publication') is not None:
            ref_expanded_text = ref_expanded_text + '\n' + ref.get('publication')
        if ref_year is not None:
            ref_small_text = ref_small_text + ', ' + ref_year
            ref_expanded_text = ref_expanded_text + ', ' + ref_year
        if ref_title is not None:
            ref_small_text = ref_small_text + ', ' + ref_title
            ref_expanded_text = ref_expanded_text + '\n' + ref_title
        if ref_doi is not None:
            ref_expanded_text = ref_expanded_text + '\n' + ref_doi
            try:
                doc_json = self.library.get_document(ref_doi, return_json=True)
                has_file = doc_json.get('file_attached')
                if has_file:
                    in_lib = 2
                else:
                    in_lib = 1
            except Exception:
                in_lib = 0

        # Cut off length of small text to fit within window
        ref_small_text = td(ref_small_text, 66)

        # Make ReferenceLabel object and set attributes
        ref_label = ReferenceLabel(ref_small_text, self)
        ref_label.small_text = ref_small_text
        ref_label.expanded_text = ref_expanded_text
        ref_label.reference = ref
        ref_label.doi = ref.get('doi')
        ref_label.status = in_lib

        # Append all labels to reference text lists in in Data()
        self.data.small_ref_labels.append(ref_small_text)
        self.data.expanded_ref_labels.append(ref_expanded_text)

        return ref_label


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Notes Box Display Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def show_main_notes_box(self):
        """
        Displays the notes/info window for the paper from the DOI in
        the main text box.
        """
        # Paper must be in the library to display the window
        if self.doc_selector.status == 0:
            _send_msg('Document not found in library.')
            return
        doc_json = self.data.doc_response_json
        if doc_json is None:
            if self.doc_selector.entry_type == 'doi':
                doi = self.doc_selector.value
                doc_json = self.library.get_document(doi=doi, return_json=True)
            else:
                raise LookupError('Need DOI to open notes box.')

        if doc_json is None:
            raise LookupError('Main document information not found')

        notes = doc_json.get('notes')

        # Add entry to history
        self.doc_selector.add_to_history(self.doc_selector.value)

        self.tnw = TabbedNotesWindow(parent=self, notes=notes, doc_json=doc_json)
        self.tnw.show()


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Misc. Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def focus(self):
        if self.encapsulating_window is not None:
            self.parent_tab_window.setCurrentWidget(self.encapsulating_window)
        else:
            self.parent_tab_window.setCurrentWidget(self)


    def update_document_status(self, doi=None, adding=False, popups=True, sync=True):
        """
        Updates the indicators about whether a certain paper is in the user's library.
        Change color of indicator.

        Parameters
        ----------
        doi : str
            DOI of the paper to check for.
        adding : bool
            Indicates whether a paper is being added or deleted.
        """
        if sync:
            self.library.sync()

        if doi is None:
            doi = self.doc_selector.value
            if doi is None:
                return

        try:
            doc_json = self.library.get_document(doi, return_json=True)
        except DocNotFoundError:
            # Document was not found in library
            if adding:
                if popups:
                    _send_msg('Document not in library.')
            self.data.doc_response_json = None
            self.doc_selector.status = 0
        except Exception:
            if adding:
                if popups:
                    _send_msg('An error occurred during sync.\nDocument may not have been added.')
            self.data.doc_response_json = None
            self.doc_selector.status = 0
        else:
            has_file = doc_json.get('file_attached')
            if has_file is not None:
                if adding:
                    # If no file is found, there may have been an error.
                    # Give users the ability to delete the document that was added without file.
                    if not has_file:
                        msgBox = QMessageBox()
                        msgBox.setText('Document was added without a file attached.\n'
                                       'If this was in error, you may choose to delete\n'
                                       'the file and add again. Otherwise, ignore this message.')
                        delete_button = QPushButton('Delete')
                        msgBox.addButton(delete_button, QMessageBox.RejectRole)
                        delete_button.clicked.connect(lambda: self.move_to_trash(doi=doi))
                        msgBox.addButton(QPushButton('Ignore'), QMessageBox.AcceptRole)

                        reply = msgBox.exec_()

                        # If the user chose to ignore, exit this function.
                        if reply != QMessageBox.Accepted:
                            # 1 = document in library without attached file
                            self.data.doc_response_json = doc_json
                            self.doc_selector.status = 1
                            return
                    else:
                        # 2 = document in library with attached file
                        self.data.doc_response_json = doc_json
                        self.doc_selector.status = 2
                else:
                    if has_file:
                        self.doc_selector.status = 2
                    else:
                        self.doc_selector.status = 1


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Internal Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def _check_lib(self, doi=None):
        """
        Checks library for a DOI, returns true if found.

        Parameters
        ----------
        doi : str
            DOI of the paper to look up.

        Returns
        -------
        in_library: bool
            True if DOI is found in the user's library.
            False otherwise.
        """
        if doi is None:
            entered_doi = self.doc_selector.value
        else: entered_doi = doi

        if entered_doi == '':
            return False
        in_library = self.library.check_for_document(entered_doi)
        return in_library

    def _set_response_message(self, message):
        """
        Sets the line of text to indicate program status.
        """
        self.response_label.setText(message)
        self.response_label.repaint()
        qApp.processEvents()
        self.response_label.show()

    def _populate_data(self, info):
        """
        Sets attributes of Data object with information about the paper
        being searched for in the main text box.

        Parameters
        ----------
        info : PaperInfo object
            See pypub.paper_info
            Holds information about a paper.
        """
        self.data.entry = info.entry
        self.data.references = info.references
        self.data.doi = info.doi
        self.data.scraper_obj = info.scraper_obj
        self.data.pdf_link = info.pdf_link
        self.data.url = info.url
        self.data.small_ref_labels = []
        self.data.expanded_ref_labels = []


class InternalSearchWindow(QWidget):
    """
    --- Overview of Usage ---
    User inputs a DOI. The indicator button to the left of the text box will
    turn green if the DOI within the text field is in the user's library.
    From there, the user can get the references for the paper, which will appear
    in a large box below the buttons, or the user can open up the notes editor,
    which appears in a smaller, new window. The notes can be edited and saved.

    --- Features ---
    * Indicator button next to the text field turns green if the entered DOI
       is found in the user's library. This is done automatically.
    * Get References button creates a list of the references for the paper
       entered in the text box. See "ReferenceLabel" for more information.
    * Open Notes button opens a new window with the Mendeley notes about
       the paper. These can be edited and saved.

    TODOs:
     - Implement URL input capability, not just DOI
     - Possibly make the window tabbed with expanded functionality?
     - Implement reading the abstract of any paper

    """
    def __init__(self, parent_tab_window=None, sibling_window=None):
        super(InternalSearchWindow, self).__init__()

        self.library = LibraryInterface.create('Mendeley')

        self.fModel = FunctionModel(self)
        self.data = Data()

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.parent_tab_window = parent_tab_window
        self.sibling_window = sibling_window
        self.main_window = self.sibling_window.centralWidget()

        self.initUI()

    def initUI(self):

        # Make all widgets
        self.entryLabel = QLabel('Please enter search information')

        self.title_box = QLineEdit()
        self.author_box = QLineEdit()
        self.publication_box = QLineEdit()
        self.year_box = QLineEdit()
        self.doi_box = QLineEdit()
        self.pmid_box = QLineEdit()

        self.title_box.setPlaceholderText('Title')
        self.author_box.setPlaceholderText('Author(s)')
        self.publication_box.setPlaceholderText('Publication')
        self.year_box.setPlaceholderText('Year')
        self.doi_box.setPlaceholderText('DOI')
        self.pmid_box.setPlaceholderText('PMID')

        self.indicator = QPushButton()
        self.refresh = QPushButton('Sync with Library')
        self.trash = QPushButton('Move to Trash')
        self.search_in_lib = QPushButton('Search in Library')
        self.history = QComboBox()
        self.response_label = QLabel()
        self.ref_area = QScrollArea()

        # Set connections to functions
        self.title_box.returnPressed.connect(self.search)
        self.author_box.returnPressed.connect(self.search)
        self.publication_box.returnPressed.connect(self.search)
        self.year_box.returnPressed.connect(self.search)
        self.doi_box.returnPressed.connect(self.search)
        self.pmid_box.returnPressed.connect(self.search)

        self.refresh.clicked.connect(self.fModel.resync)
        self.trash.clicked.connect(self.move_to_trash)
        self.search_in_lib.clicked.connect(self.search)


        # Make scroll items widget
        self.ref_items = QWidget()
        items_layout = QVBoxLayout()
        items_layout.addStretch(1)
        self.ref_items.setLayout(items_layout)
        self.ref_items_layout = self.ref_items.layout()

        # Format scrollable reference area
        self.ref_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.ref_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ref_area.setWidgetResizable(True)
        ref_layout = QVBoxLayout()
        self.ref_area.setLayout(ref_layout)
        self.ref_area_layout = self.ref_area.layout()
        self.ref_area.setWidget(self.ref_items)
        self.ref_area.hide()

        text_area_top = QHBoxLayout()
        text_area_top.addWidget(self.title_box)
        text_area_top.addWidget(self.author_box)

        text_area_bottom = QHBoxLayout()
        text_area_bottom.addWidget(self.publication_box)
        text_area_bottom.addWidget(self.year_box)
        text_area_bottom.addWidget(self.doi_box)
        text_area_bottom.addWidget(self.pmid_box)

        # Create a horizontal box to be added to vbox later
        # The radiobuttons having the same parent widget ensures
        # that they are part of a group and only one can be checked.
        checkboxes = QHBoxLayout()
        checkboxes.addWidget(self.refresh)
        checkboxes.addWidget(self.trash)
        checkboxes.addWidget(self.history)
        checkboxes.addWidget(self.search_in_lib)
        checkboxes.addStretch(1)

        # Create a vertical box layout.
        # Populate with widgets and add stretch space at the bottom.
        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.entryLabel)

        # Create a horizontal box for indicator and textEntry
        # self.doc_selector = DocSelector(window=self)
        # ds_view = self.doc_selector.text_view
        # textline = ds_view.create_text_layout(textEntry=self.textEntry, indicator=self.indicator)

        self.vbox.addLayout(text_area_top)
        self.vbox.addLayout(text_area_bottom)
        self.vbox.addLayout(checkboxes)
        self.vbox.addWidget(self.response_label)
        self.vbox.addWidget(self.ref_area)
        self.vbox.addStretch(1)

        self.response_label.hide()

        # Set layout to be the vertical box.
        self.setLayout(self.vbox)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)


    # +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+= Start of Functions

    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Main Window Button Functions
    # ++++++++++++++++++++++++++++++++++++++++++++

    def text_changed(self):
        doc_id = self.doc_selector.value
        self.update_document_status(doi=doc_id, sync=False, popups=False)

    def get_refs(self):
        """
        Gets references for paper corresponding to the DOI in text field.
        Displays reference information in scrollable area.
        """
        self.response_label.hide()

        # Get DOI from text field and handle blank entry
        entered_doi = self.doc_selector.value

        if entered_doi == '':
            self._set_response_message('Please enter text above.')
            return

        # Resolve DOI and get references
        refs = self.fModel.retrieve_only_refs(doi=entered_doi)

        if refs is None or len(refs) == 0:
            _send_msg('No references found.')
            return

        # First clean up existing GUI window.
        # If there are widgets in the layout (i.e. from the last call to 'get_refs'),
        # delete all of those reference labels before adding more.
        _delete_all_widgets(self.ref_items_layout)

        for ref in refs:
            ref_label = self.ref_to_label(ref)
            self.ref_items_layout.insertWidget(self.ref_area_layout.count() - 1, ref_label)

        # Add entry to history
        self.doc_selector.add_to_history(entered_doi)

        self.response_label.hide()
        self.ref_area.show()

    #
    # For "Open Notes", see "Notes Box Display Functions" section below.
    #

    def add_to_library_from_main(self):
        """
        Adds paper corresponding to the DOI in the text field to the user library,
        if it is not already there.
        """
        if self.doc_selector.status in (1,2):
            _send_msg('Paper is already in library.')
            return

        doi = self.doc_selector.value
        if doi is None or doi == '':
            self._set_response_message('Please enter text above.')
            return

        try:
            self.library.add_to_library(doi)
        except UnsupportedPublisherError as exc:
            error_logging.log(method='gui.Window.add_to_library_from_main', message='Unsupported publisher', error=str(exc), doi=doi)
            _send_msg('Publisher is not yet supported.\nDocument not added.')
            return
        except CallFailedException as call:
            error_logging.log(method='gui.Window.add_to_library_from_main', message='Call failed', error=str(call), doi=doi)
            _send_msg(str(call))
        except ParseException or AttributeError as exc:
            error_logging.log(method='gui.Window.add_to_library_from_main', message='Error while parsing article webpage',
                error=str(exc), doi=doi)
            _send_msg('Error while parsing article webpage.')
        except PDFError:
            _send_msg('PDF could not be retrieved.')
        except Exception as exc:
            error_logging.log(method='gui.Window.add_to_library_from_main', error=str(exc), doi=doi)
            _send_msg(str(exc))

        # Add entry to history
        self.doc_selector.add_to_history(doi)

        self.update_document_status(doi, adding=True)

    def move_to_trash(self, doi=None):
        """
        Moves a paper from the user's library to trash
        (in Mendeley).

        Parameters
        ----------
        doi : str
            DOI of the paper to be deleted.
        """

        # This method can be called with doi as None or
        # as False (which is default if connected from
        # a GUI button) so this looks for String DOIs
        if isinstance(doi, str):
            entry_type = 'doi'
            value = doi
        else:
            entry_type = self.doc_selector.entry_type
            value = self.doc_selector.value

        try:
            self.library.trash_document(**{entry_type: value})
        except DocNotFoundError:
            _send_msg('Document not found in library.')
            return
        except UnsupportedEntryTypeError:
            _send_msg('Only functions using DOIs are supported at this time.')
            return

        # Add entry to history
        self.doc_selector.add_to_history(value)

        self.update_document_status(doi=value)

    def follow_refs_forward(self):
        doi = self.doc_selector.value
        things = db.follow_refs_forward(doi)

        # First clean up existing GUI window.
        # If there are widgets in the layout (i.e. from the last call to 'get_refs'),
        # delete all of those reference labels before adding more.
        _delete_all_widgets(self.ref_items_layout)

        for thing in things:
            ref_label = self.ref_to_label(thing)
            self.ref_items_layout.insertWidget(self.ref_area_layout.count() - 1, ref_label)

        # Add entry to history
        self.doc_selector.add_to_history(doi)

        self._set_response_message('Papers in your database that cite the given DOI.\n'
                                   'List may not be exhaustive.')

        self.ref_area.show()

    def search(self):
        self.response_label.hide()

        title_text = self.title_box.text()
        author_text = self.author_box.text()
        publication_text = self.publication_box.text()
        year_text = self.year_box.text()
        doi_text = self.doi_box.text()
        pmid_text = self.pmid_box.text()

        search_dict = {'title': title_text,
                       'authors': author_text,
                       'publication': publication_text,
                       'year': year_text,
                       'doi': doi_text,
                       'pmid': pmid_text}

        # Remove any text fields that have not been filled out
        sd_copy = dict(search_dict)
        for k, v in search_dict.items():
            if v is None or v == '':
                del sd_copy[k]

        search_dict = sd_copy
        results = db.check_multiple_constraints(search_dict)

        if results is None or len(results) == 0:
            _send_msg('No matching entries found.')
            return

        # First clean up existing GUI window.
        # If there are widgets in the layout (i.e. from the last call to 'get_refs'),
        # delete all of those reference labels before adding more.
        _delete_all_widgets(self.ref_items_layout)

        for result in results:
            # ref_label = self.ref_to_label(result)
            ref_label = self.main_window.ref_to_label(result)
            self.ref_items_layout.insertWidget(0, ref_label)

        self.response_label.hide()
        self.ref_area.show()


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Notes Box Display Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def show_main_notes_box(self):
        """
        Displays the notes/info window for the paper from the DOI in
        the main text box.
        """
        # Paper must be in the library to display the window
        if self.doc_selector.status == 0:
            _send_msg('Document not found in library.')
            return
        doc_json = self.data.doc_response_json
        if doc_json is None:
            raise LookupError('Main document JSON not found')
        notes = doc_json.get('notes')

        # Add entry to history
        self.doc_selector.add_to_history(self.doc_selector.value)

        self.tnw = TabbedNotesWindow(parent=self, notes=notes, doc_json=doc_json)
        self.tnw.show()


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Misc. Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def focus(self):
        if self.sibling_window is not None:
            self.parent_tab_window.setCurrentWidget(self.sibling_window)

    def update_document_status(self, doi=None, adding=False, popups=True, sync=True):
        """
        Updates the indicators about whether a certain paper is in the user's library.
        Change color of indicator.

        Parameters
        ----------
        doi : str
            DOI of the paper to check for.
        adding : bool
            Indicates whether a paper is being added or deleted.
        """
        if sync:
            self.library.sync()

        if doi is None:
            doi = self.doc_selector.value
            if doi is None:
                return

        try:
            doc_json = self.library.get_document(doi, return_json=True)
        except DocNotFoundError:
            # Document was not found in library
            if adding:
                if popups:
                    _send_msg('Document not in library.')
            self.data.doc_response_json = None
            self.doc_selector.status = 0
        except Exception:
            if adding:
                if popups:
                    _send_msg('An error occurred during sync.\nDocument may not have been added.')
            self.data.doc_response_json = None
            self.doc_selector.status = 0
        else:
            has_file = doc_json.get('file_attached')
            if has_file is not None:
                # If no file is found, there may have been an error.
                # Give users the ability to delete the document that was added without file.
                if not has_file:
                    msgBox = QMessageBox()
                    msgBox.setText('Document was added without a file attached.\n'
                                   'If this was in error, you may choose to delete\n'
                                   'the file and add again. Otherwise, ignore this message.')
                    delete_button = QPushButton('Delete')
                    msgBox.addButton(delete_button, QMessageBox.RejectRole)
                    delete_button.clicked.connect(lambda: self.move_to_trash(doi=doi))
                    msgBox.addButton(QPushButton('Ignore'), QMessageBox.AcceptRole)

                    reply = msgBox.exec_()

                    # If the user chose to ignore, exit this function.
                    if reply != QMessageBox.Accepted:
                        # 1 = document in library without attached file
                        self.data.doc_response_json = doc_json
                        self.doc_selector.status = 1
                        return
                else:
                    # 2 = document in library with attached file
                    self.data.doc_response_json = doc_json
                    self.doc_selector.status = 2


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Internal Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def _check_lib(self, doi=None):
        """
        Checks library for a DOI, returns true if found.

        Parameters
        ----------
        doi : str
            DOI of the paper to look up.

        Returns
        -------
        in_library: bool
            True if DOI is found in the user's library.
            False otherwise.
        """
        if doi is None:
            entered_doi = self.doc_selector.value
        else: entered_doi = doi

        if entered_doi == '':
            return False
        in_library = self.library.check_for_document(entered_doi)
        return in_library

    def _set_response_message(self, message):
        """
        Sets the line of text to indicate program status.
        """
        self.response_label.setText(message)
        self.response_label.repaint()
        qApp.processEvents()
        self.response_label.show()

    def _populate_data(self, info):
        """
        Sets attributes of Data object with information about the paper
        being searched for in the main text box.

        Parameters
        ----------
        info : PaperInfo object
            See pypub.paper_info
            Holds information about a paper.
        """
        self.data.entry = info.entry
        self.data.references = info.references
        self.data.doi = info.doi
        self.data.scraper_obj = info.scraper_obj
        self.data.pdf_link = info.pdf_link
        self.data.url = info.url
        self.data.small_ref_labels = []
        self.data.expanded_ref_labels = []


class TabbedNotesWindow(QTabWidget):
    """
    This is the smaller window that appears displaying notes for a given reference.
    ...BUT NOW WITH TABS!

    --- Notes Tab Features ---
    * Text box: Displays the current notes saved for a given document, and allows
       for editing.
    * Save button: Saves the changes made to the notes, and syncs with Mendeley.
    * Save and Close button: Saves the changes made to the notes, syncs, with
       Mendeley, and closes the notes window.
    * Prompting before exit: If the user attempts to close the window after
       making unsaved changes to the notes, a pop-up window appears asking
       to confirm the action without saving. Provides an option to save.

    --- Abstract Tab Features ---
    * The abstract. I don't know what else you expected.

    --- Info Tab Features ---
    * If available, lists all paper information including authors, title,
       journal, volume, pages, and identifiers such as DOI.

    TODOs:
     - Fix the prompt before exit (currently appears when closing the main
        window, even after the notes window is gone. Maybe this has to do
        with having closed the window but not terminating the widget process?)
     - Add (automatic or voluntary) feature to input a little note saying something
        like "edited with reference to [original file that references this one]"

    """
    def __init__(self, parent=None, notes=None, doc_json=None, label=None):
        super(TabbedNotesWindow, self).__init__()
        self.parent = parent
        self.notes = notes
        self.doc_json = doc_json
        self.doi = None
        self.doc_id = None
        self.caption = None
        self.label = label

        if self.label is not None:
            ref_dict = getattr(label, 'reference', None)
            if ref_dict is not None:
                self.doi = ref_dict.get('doi')
                self.make_captions(ref_dict=ref_dict)
        if self.doc_json is not None:
            self.doi = self.doc_json.get('doi')
            self.doc_id = self.doc_json.get('id')
            self.make_captions(doc_json=self.doc_json)

        self.setWindowTitle(self.caption)

        # Connect keyboard shortcut
        self.close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.close_shortcut.activated.connect(self.close)

        # Make tabs
        self.notes_tab = QWidget()
        self.abstract_tab = QWidget()
        self.info_tab = QWidget()

        self.addTab(self.notes_tab, 'Notes')
        self.addTab(self.abstract_tab, 'Abstract')
        self.addTab(self.info_tab, 'Info')
        self.notesUI()
        self.abstractUI()
        self.infoUI()

        if self.notes is not None:
            self.notes_box.setText(self.notes)

        self.saved = True

        self.show()

    def notesUI(self):
        # Make widgets
        self.notes_title = QLabel('Notes:')
        self.saving_status = QStackedWidget()
        self.saving_label = QLabel('Saving...')
        self.saved_label = QLabel('Saved!')
        self.notes_box = QTextEdit()
        self.save_button = QPushButton('Save')
        self.save_and_close_button = QPushButton('Save and Close')

        # Populate saving_status label
        self.saving_label.setStyleSheet("color:blue;")
        self.saved_label.setStyleSheet("color:grey;")
        self.saving_status.addWidget(self.saving_label)
        self.saving_status.addWidget(self.saved_label)
        self.saving_status.hide()

        # Connect widgets
        self.save_button.clicked.connect(self.save)
        self.save_and_close_button.clicked.connect(self.save_and_close)
        self.notes_box.textChanged.connect(self.updated_text)

        if self.notes is not None:
            self.notes_box.setText(self.notes)

        self.saved = True

        titlebox = QHBoxLayout()
        titlebox.addWidget(self.notes_title)
        titlebox.addStretch(1)
        titlebox.addWidget(self.saving_status)

        hbox = QHBoxLayout()
        hbox.addWidget(self.save_button)
        hbox.addWidget(self.save_and_close_button)

        # Make layout and add widgets
        vbox = QVBoxLayout()
        vbox.addLayout(titlebox)
        vbox.addWidget(self.notes_box)
        vbox.addStretch(1)

        vbox.addLayout(hbox)

        self.notes_tab.setLayout(vbox)

    def abstractUI(self):
        abstract = self.doc_json.get('abstract')

        abstract_label = QLabel(abstract)
        abstract_label.setWordWrap(True)
        abstract_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        abstract_layout = QVBoxLayout()
        abstract_layout.addWidget(abstract_label)

        self.abstract_tab.setLayout(abstract_layout)


    def infoUI(self):

        # list of things to include:
        # publisher, authors, year, doi, title, identifiers(?), pages, volume

        info = ''
        if self.doc_json.get('title') is not None:
            info = info + 'Title: ' + self.doc_json.get('title') + '\n'
        author_list = self.doc_json.get('authors')
        authors = ''
        if author_list is not None:
            for author in author_list:
                authors = authors + author['first_name'] + ' ' + author['last_name'] + ', '
            authors = authors[:-2] # Get rid of trailing comma
        info = info + 'Authors: ' + authors + '\n'
        if self.doc_json.get('publisher') is not None:
            info = info + 'Publisher: ' + self.doc_json.get('publisher') + ','
        if self.doc_json.get('year') is not None:
            info = info + str(self.doc_json.get('year')) + '\n'
        if self.doc_json.get('volume') is not None:
            info = info + 'Volume: ' + self.doc_json.get('volume').strip() + ', '
        if self.doc_json.get('issue') is not None:
            info = info + 'Issue: ' + self.doc_json.get('issue') + '\n'
        if self.doc_json.get('pages') is not None:
            info = info + 'Pages: ' + self.doc_json.get('pages') + '\n'
        ids = self.doc_json.get('identifiers')
        if ids is not None:
            info = info + 'Identifiers: '
            for key in ids.keys():
                info = info + key.upper() + ': ' + ids.get(key) + ', '
            info = info[:-2] # Get rid of trailing comma

        info_label = QLabel(info)
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_label.setWordWrap(True)

        info_layout = QVBoxLayout()
        info_layout.addWidget(info_label)

        self.info_tab.setLayout(info_layout)

    def make_captions(self, doc_json=None, ref_dict=None):
        if ref_dict is not None:
            doc_title = ref_dict.get('ref_title')
            doc_year = ref_dict.get('ref_year')
            doc_authors = ref_dict.get('ref_author_list')
            first_authors = ref_dict.get('ref_first_authors')
        else:
            # Make a useful window title
            doc_title = doc_json.get('title')
            doc_year = doc_json.get('year')
            doc_authors = doc_json.get('authors')
            if doc_authors is not None:
                lastnames = [a.get('last_name') for a in doc_authors]
                first_authors = lastnames[0:2]
                first_authors = ', '.join(first_authors)
                if len(lastnames) > 2:
                    first_authors = first_authors + ', et al.'
            else:
                first_authors = ''

        self.caption = ''

        if doc_year is not None and doc_authors is not None:
            self.caption = first_authors + ' (' + str(doc_year) + ')'
        elif doc_title is not None:
            self.caption = doc_title
        else:
            self.caption = self.doi

    def save(self):
        # Change label to indicate saving
        self.saving_status.setCurrentIndex(0)
        self.saving_status.show()

        # Get plaintext notes from the notes box
        # TODO: figure out how to get newline statements to appear
        updated_notes = self.notes_box.toPlainText()
        notes_dict = {"notes" : updated_notes}

        # Update the Mendeley document with the new notes and sync with library
        self.parent.library.update_document(doc_id=self.doc_id, notes=notes_dict)
        self.parent.library.sync()

        # Update local version of notes to updated version and indicate saved
        if self.label is None:
            self.parent.data.doc_response_json['notes'] = updated_notes
        self.saved = True

        # Change label to indicate saved
        self.saving_status.setCurrentIndex(1)
        self.saving_status.show()
        QTimer.singleShot(2000, self.saving_status.hide)

    def save_and_close(self):
        self.save()
        self.close()

    def updated_text(self):
        self.saved = False

    def closeEvent(self, QCloseEvent):
        if self.saved:
            QCloseEvent.accept()
            return
        else:
            reply = QMessageBox.question(self, 'Message', 'Notes have not been saved.\n'
                      'Are you sure you want to close notes?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            QCloseEvent.accept()
        else:
            QCloseEvent.ignore()


class DocSelectorView(object):

    # - text entry
    # - type selectors
    
    def __init__(self, window):
        self.window = window
        self._status = 0

        self.indicator = self.window.indicator
        self.textEntry = self.window.textEntry
        self.history = self.window.history

        self.history.activated[str].connect(self.set_history_text)
        self.history.setInsertPolicy = QComboBox.InsertAtTop

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self,value):
        # Document is found in the library with file attached
        if value == 2:         
            self.indicator.setStyleSheet("""QPushButton {
                                                background-color: rgba(0,255,0,0.25); }""")
            self._status = 2

        elif value == 1:
            self.window.indicator.setStyleSheet("""QPushButton {
                                                background-color: rgba(255,165,0,0.25); }""")
            self._status = 1
        elif value == 0:
            self.window.indicator.setStyleSheet("""QPushButton {
                                            background-color: rgba(255, 0, 0, 0.25); }""")
        else:
            raise ValueError('Invalid ')

    def create_text_layout(self, textEntry, indicator):
        #   TODO: Also handle initialization of callbacks
        indicator.setStyleSheet("""QPushButton {
                                       background-color: rgba(0,0,0,0.25);
                                       }""")
        indicator.setAutoFillBackground(True)
        indicator.setFixedSize(20,20)
        indicator.setToolTip("Green: doc DOI in library.\n"
                             "Yellow: doc missing file.\n"
                             "Red: no doc with DOI found.")

        textline = QHBoxLayout()
        textline.addWidget(indicator)
        textline.addWidget(textEntry)
        return textline

    def set_history_text(self, historical_entry):
        self.textEntry.setText(historical_entry)

    def add_to_history(self, entry):
        num_items = self.history.count()

        # Make sure the same item isn't added twice in a row
        if self.history.itemText(0) == entry:
            return

        if num_items > 20:
            self.history.removeItem(num_items-1)
            # self.history.addItem(entry)
            self.history.insertItem(0, entry)
            self.history.setCurrentIndex(0)
        else:
            # self.history.addItem(entry)
            self.history.insertItem(0, entry)
            self.history.setCurrentIndex(0)


class DocSelector(object):
    
    """

    New layout:
    -----------
    view_callback => main_window.view_changed

    #method in "window"
    def view_changed(self):
        type = self.doc_selector.type
        value = self.doc_selector.value
        
        if type == 'doi'
            response = self.library.check_document_status(doi=value)
            
        self.doc_selector.status = response.status

        if response.status > 0
          #Then update the references   


    self.library.sync
    self.doc_selector.status = 0
    
    """    

    def __init__(self, window):
        self.window = window
        self.text_view = DocSelectorView(self.window)

        # Set int to keep track of if a DOI is in the library
        # 0 --> DOI is not found in library (indicator red)
        # 1 --> DOI is found, but there is no file (indicator orange)
        # 2 --> DOI is found, with file attached (indicator green)
        self._status = 0

        self.type_selector_objs = [self.window.doi_check, self.window.url_check,
                                   self.window.fulltext_check, self.window.pmid_check]
        self.type_selector_names = ['doi', 'url', 'fulltext', 'pmid']

    @property
    def entry_type(self):
        for x in range(0, len(self.type_selector_objs)):
            if self.type_selector_objs[x].isChecked():
                return self.type_selector_names[x]

    @property
    def value(self):
        text = self.window.textEntry.text()
        text = text.strip()
        return text

    # TODO: implement this
    @property
    def has_entry(self):
        return False

    # TODO: implement this
    @property
    def has_attached_file(self):
        return False

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        # This method can be called by the window when:
        # 1) Processing the current information to "load" a document
        # 2) Upon deleting a document
        # 3) Upon syncing

        self._status = value

        # Update main paper entry to reflect presence of attached file
        if self.entry_type == 'doi':
            if value == 0:
                has_file = 0
                in_lib = 0
            elif value == 1:
                has_file = 0
                in_lib = 1
            elif value == 2:
                has_file = 1
                in_lib = 1
            else:
                has_file = None
                in_lib = None

            db.update_entry_field(identifying_value=self.value, updating_field=['has_file', 'in_lib'],
                                  updating_value=[has_file, in_lib], filter_by_doi=True)

        self.text_view.status = value  # This should call a setter method that redraws accordingly

    def add_to_history(self, entry):
        self.text_view.add_to_history(entry)


class FunctionModel(object):
    def __init__(self, window):
        # Pass in the instance of the EntryWindow
        self.window = window

    '''
    def retrieve_refs(self, doi):
        refs = []
        try:
            self.window._set_response_message('Querying Scopus...')
            paper_info = rr.retrieve_all_info(input=doi, input_type='doi')
            refs = paper_info.references

            self.window._populate_data(paper_info)

        except UnsupportedPublisherError as exc:
            error_logging.log(method='gui.Window.get_refs', message='Unsupported Publisher', error=str(exc), doi=doi)
            _send_msg('Unsupported Publisher')
            return
        except ParseException or AttributeError as exc:
            error_logging.log(method='gui.Window.get_refs', message='Error parsing journal page', error=str(exc), doi=doi)
            _send_msg('Error parsing journal page')
            return
        #except Exception as exc:
        #    log(method='gui.Window.get_refs', error=str(exc), doi=doi)
        #    _send_msg(str(exc))

        return refs
    '''

    def retrieve_only_refs(self, doi):
        refs = []
        try:
            refs = rr.retrieve_only_references(input=doi, input_type='doi')

            self.window.data.references = refs

        except UnsupportedPublisherError as exc:
            error_logging.log(method='gui.Window.get_refs', message='Unsupported Publisher', error=str(exc), doi=doi)
            _send_msg('Unsupported Publisher')
            return
        except ParseException or AttributeError as exc:
            error_logging.log(method='gui.Window.get_refs', message='Error parsing journal page', error=str(exc), doi=doi)
            _send_msg('Error parsing journal page')
            return
        except Exception as exc:
           error_logging.log(method='gui.Window.get_refs', error=str(exc), doi=doi)
           _send_msg(str(exc))

        return refs

    def add_all_refs(self, main_doi, ref_labels):
        for x in range(1, ref_labels.count()):
            label = ref_labels.itemAt(x).widget()
            doi = label.doi
            self.window.response_label.setText('Adding: ' + label.small_text)
            self.window.response_label.repaint()
            qApp.processEvents()

            label.add_to_library_from_label(doi, index=x, referencing_paper=main_doi, popups=False,
                update_status=False, adding_all=True)

        # Sync the library
        self.window.library.sync()

        # Update all of the labels
        for x in range(1, ref_labels.count()):
            label = ref_labels.itemAt(x).widget()
            label.update_status(doi=label.doi, adding=True, popups=False, sync=False)

    def resync(self, main_window=True):
        self.window._set_response_message('Re-syncing with Mendeley...')
        self.window.library.sync()

        # If references are visible, update their status and label color
        if self.window.ref_items_layout.count() > 1:
            for x in range(1, self.window.ref_items_layout.count()):
                label = self.window.ref_items_layout.itemAt(x).widget()
                label.update_status(adding=False, popups=False, sync=False)

        # This does not run if resync is called from the manual reference entry window.
        if main_window:
            self.window.update_document_status(adding=False, popups=False, sync=False)
        self.window.response_label.hide()


class ReferenceLabel(QLabel):
    """
    Custom extension of QLabel to allow several types of clicking functionality.

    --- Features ---
     * Click once on a reference to expand it downward and view more information,
        including the full title, the journal it appears in, and its DOI.
     * Click twice on a reference to open up the notes editor for that reference
        (though the reference must first be in the user's library). If the reference
        is not already in the user's library, a pop-up window asks if they would
        like to add it.
     * Reference entry is highlighted in green if it exists in the user's library,
        red if the reference is not in the library, or grey if there is no DOI listed.
     * Right-click menu options:
        - Add to library
           The reference information and file is retrieved using a web scraper and
            added to the user's Mendeley library.
           Requires that the user has the appropriate permissions to access the file
            through the publisher, and that there is a web scraper in place for that
            specific publisher.
        - Look up references
           The DOI of the reference is searched for, and its references listed.
           Requires that the reference has a DOI.
        - Move to trash
           Moves the document and file from the user's Mendeley library to the trash.
           Requires that the document be in the user's library.
    """

    def __init__(self, text, parent):
        super().__init__()

        self.parent = parent
        self.view = RefLabelView(self)

        self.metrics = QFontMetrics(self.font())
        elided = self.metrics.elidedText(text, Qt.ElideRight, self.width())

        self.setText(text)
        self.expanded_text = None
        self.small_text = None
        self.reference = None
        self.doi = None

        self.menu = QMenu(self)
        self.add_to_lib = self.menu.addAction("Add to library")
        self.ref_lookup = self.menu.addAction("Look up references")
        self.ref_follow_forward = self.menu.addAction("Follow refs forward")
        self.move_to_trash = self.menu.addAction("Move to trash")
        self.add_doi = self.menu.addAction("Find DOI")
        self.manual_ref_entry = self.menu.addAction("Manual Reference Entry")
        self.copy_doi = self.menu.addAction("Copy DOI")
        self.menu.setStyleSheet("QMenu { background-color: #d9d9d9; }")

        self.ClickFilter = ClickFilter(self)
        self.installEventFilter(self.ClickFilter)

        # Connect click to expanding the label
        # Connect double click to opening notes/info window
        self.ClickFilter.clicked.connect(self.change_ref_label)
        self.ClickFilter.doubleclicked.connect(self.show_ref_notes_box)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setWordWrap(True)

    def change_ref_label(self):
        """
        Expands or compresses reference label on click
        """
        clicked_label = self.sender().parent

        label_text = clicked_label.text()
        if label_text == clicked_label.small_text:
            clicked_label.setText(clicked_label.expanded_text)
        else:
            clicked_label.setText(clicked_label.small_text)

    def show_ref_notes_box(self):
        """
        Displays the notes/info window for a paper double-clicked
        from the references window.
        """
        # label = self.sender().parent
        if self.doi is None:
            _send_msg('No DOI found for this paper.')
            return

        try:
            doc_response_json = self.parent.library.get_document(self.doi, return_json=True)
        except DOINotFoundError:
            reply = QMessageBox.question(self.parent,'Message', 'Document not found in library.\nWould you like to add it?',
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.add_to_library_from_label(self.doi)
                return
            else:
                return
        except Exception as exe:
            _send_msg(str(exe))
            return

        notes = doc_response_json.get('notes')
        self.tnw = TabbedNotesWindow(parent=self.parent, notes=notes, doc_json=doc_response_json, label=self)
        self.tnw.show()

    def update_status(self, doi=None, adding=False, popups=True, sync=True):
        """
        Updates the indicators about whether a certain paper is in the user's library.
        If from a reference label, change color of that label.

        Parameters
        ----------
        doi : str
            DOI of the paper to check for.
        adding : bool
            Indicates whether a paper is being added or deleted.
        """
        if sync:
            self.parent.library.sync()

        # A DOI is supplied to this function if it is being added to the label.
        if doi is not None:
            adding_doi = doi
            if self.doi is None:
                self.doi = adding_doi
            else:
                if self.doi != adding_doi:
                    msgBox = QMessageBox()
                    msgBox.setText('The current DOI, %s, for the document with title %s is trying to be '
                                   'replaced by the DOI %s. Is this correct?')
                    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

                    reply = msgBox.exec_()

                    # If the user chose yes, overwrite current DOI with new DOI.
                    if reply == QMessageBox.Yes:
                        self.doi = adding_doi

        doi = self.doi
        if doi is None:
            return

        try:
            doc_json = self.parent.library.get_document(doi, return_json=True)
        except DocNotFoundError:
            # Document was not found in library
            if popups:
                _send_msg('Document not in library.')
            self.status = 0
        except Exception:
            if adding:
                if popups:
                    _send_msg('An error occurred during sync.\nDocument may not have been added.')
            self.status = 0
        else:
            has_file = doc_json.get('file_attached')
            if adding:
                if has_file is not None:
                    # If no file is found, there may have been an error.
                    # Give users the ability to delete the document that was added without file.
                    if not has_file:
                        msgBox = QMessageBox()
                        msgBox.setText('Document was added without a file attached.\n'
                                       'Automatic PDF retrieval may have failed.\n'
                                       'If this was in error, you may choose to delete\n'
                                       'the document and attempt to add again. Otherwise, ignore this message.')
                        delete_button = QPushButton('Delete')
                        msgBox.addButton(delete_button, QMessageBox.RejectRole)
                        delete_button.clicked.connect(lambda: self.move_doc_to_trash(doi=doi))
                        msgBox.addButton(QPushButton('Ignore'), QMessageBox.AcceptRole)

                        reply = msgBox.exec_()

                        # If the user chose to delete, exit this function.
                        if reply != QMessageBox.Accepted:
                            return

            if has_file is not None:
                if has_file:
                    self.status = 2
                else:
                    self.status = 1
            else:
                self.status = 2

    @property
    def status(self):
        return self.view.status

    @status.setter
    def status(self, value):
        if value is not None:
            self.view.status = value
            if value == 0:
                has_file = 0
                in_lib = 0
            elif value == 1:
                has_file = 0
                in_lib = 1
            elif value == 2:
                has_file = 1
                in_lib = 1
            else:
                has_file = None
                in_lib = None
        else:
            has_file = None
            in_lib = None

        if self.doi is not None:
            db.update_entry_field(identifying_value=self.doi, updating_field=['has_file', 'in_lib'],
                                  updating_value=[has_file, in_lib], filter_by_doi=True)

    def contextMenuEvent(self, QContextMenuEvent):
        action = self.menu.exec_(self.mapToGlobal(QContextMenuEvent.pos()))
        if action == self.add_to_lib:
            self.add_to_library_from_label(self.doi)
        elif action == self.ref_lookup:
            self.lookup_ref(self.doi)
        elif action == self.ref_follow_forward:
            self.follow_forward(self.doi)
        elif action == self.move_to_trash:
            self.move_doc_to_trash(self.doi)
        elif action == self.add_doi:
            self.add_doi()
        elif action == self.manual_ref_entry:
            self.ref_entry()
        elif action == self.copy_doi:
            self.copy_doi_to_clipboard()

    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Reference Label Right-Click Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def add_to_library_from_label(self, doi, index=None, referencing_paper=None, popups=True,
                                  update_status=True, adding_all=False):
        """
        Adds reference paper to library from right-clicking on a label.

        Parameters
        ----------
        label : ReferenceLabel
            The label that was clicked.
        doi : str
            DOI of the paper in the clicked label.
        popups : bool
            If False, suppresses warning pop-up windows.
        """
        # Check that there is a DOI
        if doi is None:
            if popups:
                _send_msg('No DOI found for this reference')
            return

        # Check that the paper isn't already in the user's library
        # If all references are added at once, there are no library syncs in between, so
        # check database for duplicates before adding.
        if adding_all:
            if db.check_for_document(doi):
                if popups:
                    _send_msg('Paper is already in library.')
        # If one reference is being added at a time, check the library for duplicates
        # before adding.
        else:
            if self.parent._check_lib(doi):
                if popups:
                    _send_msg('Paper is already in library.')
                return

        self.parent.focus()

        # Try to add, have separate windows for each possible error
        try:
            self.parent.library.add_to_library(doi)
        except UnsupportedPublisherError as exc:
            error_logging.log(method='gui.Window.add_to_library_from_label', message='Publisher unsupported', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                _send_msg('Publisher is not yet supported.\n'
                                    'Document not added.')
            return
        except CallFailedException as call:
            error_logging.log(method='gui.Window.add_to_library_from_label', message='Call failed', error=str(call), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                _send_msg(str(call))
            return
        except ParseException as exc:
            error_logging.log(method='gui.Window.add_to_library_from_label', message='Error parsing webpage', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                _send_msg(str(exc))
        except TypeError or AttributeError as exc:
            error_logging.log(method='gui.Window.add_to_library_from_label', message='Error parsing webpage', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                _send_msg('Error parsing page.')
        except Exception as exc:
            error_logging.log(method='gui.Window.add_to_library_from_label', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                _send_msg(str(exc))

        if update_status:
            self.update_status(doi, adding=True, popups=popups)

    def lookup_ref(self, doi):
        """
        Sets the DOI of the clicked label in the text box and looks
        up/displays the references for that paper.

        Parameters
        ----------
        doi : str
            DOI of the clicked label
        """
        if doi is None:
            _send_msg('No DOI found for this reference')
            return
        self.parent.textEntry.setText(doi)
        self.parent.focus()
        self.parent.get_refs()

    def follow_forward(self, doi):
        """
        Sets the DOI of the clicked label in the text box and
        gets the list of papers in the user's database that
        cite the clicked label.

        Parameters
        ----------
        doi : str
            DOI of the clicked label
        """
        if doi is None:
            _send_msg('No DOI found for this reference')
            return
        self.parent.textEntry.setText(doi)
        self.parent.focus()
        self.parent.follow_refs_forward()

    def move_doc_to_trash(self, doi=None):
        """
        Moves a paper from the user's library to trash
        (in Mendeley).

        Parameters
        ----------
        doi : str
            DOI of the paper to be deleted.
        """
        if doi is None:
            doi = self.doi
        self.parent.library.trash_document(doi=doi)
        self.update_status(doi)

    def add_doi(self):
        """
        Attempts to retrieve DOI corresponding to the reference.
        """
        citing_doi = self.parent.doc_selector.value

        if self.doi is not None:
            return

        authors = self.reference.get('authors')
        date = self.reference.get('year')
        if date is None:
            date = self.reference.get('date')

        lookup = self.expanded_text
        lookup = lookup.replace('\n', ' ')
        doi, retrieved_title = rr.doi_and_title_from_citation(lookup)
        if doi is not None and '10.' in doi:
            self.doi = doi
            self.reference['doi'] = doi
            title = self.reference.get('title')

            # This is if there is no title in a given reference
            if title is None:
                title = retrieved_title
                self.reference.title = title
                if title is not None:
                    if len(title) > 60:
                        short_title = title[0:60]
                    else:
                        short_title = title
                    self.small_text = self.small_text + short_title
                    self.expanded_text = self.expanded_text + '\n' + title

            self.expanded_text = self.expanded_text + '\n' + doi

            if authors is not None:
                # Update the reference entry within the database to
                # reflect the change.
                db.update_reference_field(identifying_value=date, updating_field=['doi', 'title'],
                                        updating_value=[doi, title], citing_doi=citing_doi,
                                        authors=authors, filter_by_authors=True)
            elif title is not None:
                # Update the reference entry within the database to
                # reflect the change.
                db.update_reference_field(identifying_value=title, updating_field=['doi', 'title'],
                                    updating_value=[doi, title], filter_by_title=True)
        self.update_status(doi=doi, popups=False)

    def ref_entry(self):
        # if self.status != 2:
        #     _send_msg('Paper must be in library and have an attached PDF for manual reference entry.')
        #     return

        self.parent.textEntry.setText(self.doi)
        self.parent.focus()
        self.parent.ref_entry()

    def copy_doi_to_clipboard(self):
        if self.doi is not None:
            _copy_to_clipboard(self.doi)


class RefLabelView(object):
    def __init__(self, label):
        self._status = 0
        self.parent = label

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        # Make widget background color green if document is in library.
        # Red if not in library.
        # Neutral if there is no DOI
        self._status = value

        if value == 2:
            self.parent.setStyleSheet("background-color: rgba(0,255,0,0.25);")
        elif value == 1:
            self.parent.setStyleSheet("background-color: rgba(255,165,0,0.25);")
        elif value == 0:
            self.parent.setStyleSheet("background-color: rgba(255,0,0,0.25);")
        return


class ReferenceEntryLabel(ReferenceLabel):
    def __init__(self, text, parent):
        super().__init__(text=text, parent=parent)
        self.delete_ref = self.menu.addAction("Delete Reference")
        self.menu.setStyleSheet("QMenu { background-color: #d9d9d9; }")

    def contextMenuEvent(self, QContextMenuEvent):
        action = self.menu.exec_(self.mapToGlobal(QContextMenuEvent.pos()))
        if action == self.delete_ref:
            self.delete_reference()

    def delete_reference(self):
        db.delete_reference(self.reference)
        self.parent.remove_label(self)


class ReferenceEntryWindow(QWidget):
    """
    --- Overview of Usage ---
    User inputs a DOI. The indicator button to the left of the text box will
    turn green if the DOI within the text field is in the user's library.
    From there, the user can get the references for the paper, which will appear
    in a large box below the buttons, or the user can open up the notes editor,
    which appears in a smaller, new window. The notes can be edited and saved.

    --- Features ---
    * Indicator button next to the text field turns green if the entered DOI
       is found in the user's library. This is done automatically.
    * Get References button creates a list of the references for the paper
       entered in the text box. See "ReferenceLabel" for more information.
    * Open Notes button opens a new window with the Mendeley notes about
       the paper. These can be edited and saved.

    TODOs:
     - Implement URL input capability, not just DOI
     - Possibly make the window tabbed with expanded functionality?
     - Implement reading the abstract of any paper

    """
    def __init__(self, main_paper_doi, library, references=None):
        super(ReferenceEntryWindow, self).__init__()

        self.fModel = FunctionModel(self)
        self.data = Data()

        self.main_paper_doi = main_paper_doi
        self.library = library
        self.references = references

        self.doi_list = []
        self.title_list = []
        if self.references is not None:
            for ref in references:
                self.doi_list.append(ref.doi)
                self.title_list.append(ref.title)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.initUI()

    def initUI(self):

        # Make all widgets
        self.entryLabel = QLabel('Please enter a reference')

        self.ref_id_box = QLineEdit()
        self.title_box = QLineEdit()
        self.author_box = QLineEdit()
        self.publication_box = QLineEdit()
        self.year_box = QLineEdit()
        self.doi_box = QLineEdit()
        self.pmid_box = QLineEdit()
        self.volume_box = QLineEdit()
        self.issue_box = QLineEdit()
        self.series_box = QLineEdit()
        self.date_box = QLineEdit()
        self.pages_box = QLineEdit()
        self.full_citation_box = QLineEdit()

        self.ref_id_box.setPlaceholderText('Reference Number')
        self.title_box.setPlaceholderText('Title')
        self.author_box.setPlaceholderText('Author(s)')
        self.publication_box.setPlaceholderText('Publication')
        self.year_box.setPlaceholderText('Year')
        self.doi_box.setPlaceholderText('DOI')
        self.pmid_box.setPlaceholderText('PMID')
        self.volume_box.setPlaceholderText('Volume')
        self.issue_box.setPlaceholderText('Issue')
        self.series_box.setPlaceholderText('Series')
        self.date_box.setPlaceholderText('Date')
        self.pages_box.setPlaceholderText('Pages')
        self.full_citation_box.setPlaceholderText('Full Citation')

        self.widget_list = [self.title_box, self.author_box, self.publication_box, self.year_box,
                            self.doi_box, self.pmid_box, self.volume_box, self.issue_box, self.series_box,
                            self.date_box, self.pages_box, self.full_citation_box]

        self.indicator = QPushButton()
        self.refresh = QPushButton('Sync with Library')
        self.get_refs_button = QPushButton('Get/Display References')
        self.enter_button = QPushButton('Submit Reference')
        self.clear_button = QPushButton('Clear Fields')
        self.response_label = QLabel()
        self.ref_area = QScrollArea()

        # Set connections to functions
        self.ref_id_box.returnPressed.connect(self.submit)
        self.title_box.returnPressed.connect(self.submit)
        self.author_box.returnPressed.connect(self.submit)
        self.publication_box.returnPressed.connect(self.submit)
        self.year_box.returnPressed.connect(self.submit)
        self.doi_box.returnPressed.connect(self.submit)
        self.pmid_box.returnPressed.connect(self.submit)
        self.volume_box.returnPressed.connect(self.submit)
        self.issue_box.returnPressed.connect(self.submit)
        self.series_box.returnPressed.connect(self.submit)
        self.date_box.returnPressed.connect(self.submit)
        self.pages_box.returnPressed.connect(self.submit)
        self.full_citation_box.returnPressed.connect(self.submit)


        self.refresh.clicked.connect(self.fModel.resync)
        self.get_refs_button.clicked.connect(self.get_refs)
        self.enter_button.clicked.connect(self.submit)
        self.clear_button.clicked.connect(lambda: self._reset_forms(next_id=False))


        # Make scroll items widget
        self.ref_items = QWidget()
        items_layout = QVBoxLayout()
        items_layout.addStretch(1)
        self.ref_items.setLayout(items_layout)
        self.ref_items_layout = self.ref_items.layout()

        # Format scrollable reference area
        self.ref_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.ref_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ref_area.setWidgetResizable(True)
        ref_layout = QVBoxLayout()
        self.ref_area.setLayout(ref_layout)
        self.ref_area_layout = self.ref_area.layout()
        self.ref_area.setWidget(self.ref_items)
        self.ref_area.hide()

        text_area_top = QHBoxLayout()
        text_area_top.addWidget(self.ref_id_box)
        text_area_top.addWidget(self.title_box)
        text_area_top.addWidget(self.author_box)

        text_area_middle = QHBoxLayout()
        text_area_middle.addWidget(self.publication_box)
        text_area_middle.addWidget(self.volume_box)
        text_area_middle.addWidget(self.issue_box)
        text_area_middle.addWidget(self.series_box)

        text_area_bottom = QHBoxLayout()
        text_area_bottom.addWidget(self.date_box)
        text_area_bottom.addWidget(self.year_box)
        text_area_bottom.addWidget(self.doi_box)
        text_area_bottom.addWidget(self.pmid_box)
        text_area_bottom.addWidget(self.pages_box)
        text_area_bottom.addWidget(self.full_citation_box)


        # Create a horizontal box to be added to vbox later
        # The radiobuttons having the same parent widget ensures
        # that they are part of a group and only one can be checked.
        checkboxes = QHBoxLayout()
        checkboxes.addWidget(self.refresh)
        checkboxes.addWidget(self.get_refs_button)
        checkboxes.addWidget(self.enter_button)
        checkboxes.addWidget(self.clear_button)
        checkboxes.addStretch(1)

        # Create a vertical box layout.
        # Populate with widgets and add stretch space at the bottom.
        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.entryLabel)

        self.vbox.addLayout(text_area_top)
        self.vbox.addLayout(text_area_middle)
        self.vbox.addLayout(text_area_bottom)
        self.vbox.addLayout(checkboxes)
        self.vbox.addWidget(self.response_label)
        self.vbox.addWidget(self.ref_area)
        self.vbox.addStretch(1)

        self.response_label.hide()

        # Set layout to be the vertical box.
        self.setLayout(self.vbox)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.display_refs(refs=self.references)

        self.resize(800,700)
        _center(self)
        self.setWindowTitle('Enter Paper References')
        self.show()

    # +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+= Start of Functions

    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Main Window Button Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def get_refs(self):
        """
        Gets references for paper corresponding to the DOI in text field.
        Displays reference information in scrollable area.
        """
        if self.main_paper_doi == '':
            self._set_response_message('Please enter text above.')
            return

        # Resolve DOI and get references
        refs = self.fModel.retrieve_only_refs(doi=self.main_paper_doi)

        if refs is None or len(refs) == 0:
            self.data.references = None
            _send_msg('No references found.')
            return

        self.display_refs(refs)

    def submit(self):
        self.response_label.hide()

        ref_id_text = self.ref_id_box.text()
        title_text = self.title_box.text()
        author_text = self.author_box.text()
        publication_text = self.publication_box.text()
        year_text = self.year_box.text()
        doi_text = self.doi_box.text()
        pmid_text = self.pmid_box.text()
        volume_text = self.volume_box.text()
        issue_text = self.issue_box.text()
        series_text = self.series_box.text()
        date_text = self.date_box.text()
        pages_text = self.pages_box.text()
        full_citation_text = self.full_citation_box.text()

        ref_dict = {'ref_id':ref_id_text, 'title': title_text, 'authors': author_text,
                       'publication': publication_text, 'year': year_text, 'doi': doi_text, 'pmid': pmid_text,
                       'volume': volume_text, 'issue': issue_text, 'series': series_text, 'date': date_text,
                       'pages': pages_text, 'citation': full_citation_text}

        # Remove any text fields that have not been filled out
        sd_copy = dict(ref_dict)
        for k, v in ref_dict.items():
            if v is None or v == '':
                del sd_copy[k]
        ref_dict = sd_copy

        # Warn the user about adding duplicates
        if title_text in self.title_list:
            msgBox = QMessageBox()
            msgBox.setText('There is already a reference with the given title.\n'
                           'Would you still like to add this reference?')
            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            reply = msgBox.exec_()

            # If the user chooses No, do nothing.
            if reply == QMessageBox.No:
                return
        elif doi_text in self.doi_list:
            msgBox = QMessageBox()
            msgBox.setText('There is already a reference with the given DOI.\n'
                           'Would you still like to add this reference?')
            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

            reply = msgBox.exec_()

            # If the user chooses No, do nothing.
            if reply == QMessageBox.No:
                return

        db.add_reference([ref_dict], main_doi=self.main_paper_doi)
        label = self.ref_to_label(ref=ref_dict)
        self.ref_items_layout.insertWidget(self.ref_area_layout.count() - 1, label)

        self._reset_forms()

        self.response_label.hide()
        self.ref_area.show()

    def display_refs(self, refs=None):
        """
        Gets references for paper corresponding to the DOI in text field.
        Displays reference information in scrollable area.
        """
        self.response_label.hide()

        if refs is None:
            return

        # Get DOI from text field and handle blank entry
        entered_doi = self.main_paper_doi

        if refs is None or len(refs) == 0:
            return

        # First clean up existing GUI window.
        # If there are widgets in the layout (i.e. from the last call to 'get_refs'),
        # delete all of those reference labels before adding more.
        _delete_all_widgets(self.ref_items_layout)

        for ref in refs:
            ref_label = self.ref_to_label(ref)
            self.ref_items_layout.insertWidget(self.ref_area_layout.count() - 1, ref_label)
            self.doi_list.append(ref.doi)
            self.title_list.append(ref.title)

        self.response_label.hide()
        self.ref_area.show()

    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Reference Label Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def ref_to_label(self, ref):
        """
        Creates a ReferenceLabel object from a single paper reference.
        Formats title, author information for display, connects functionality
        to the label object.
        Used by get_refs().

        Parameters
        ----------
        ref: dict
            Contains information from a single paper reference.

        Returns
        -------
        ref_label: ReferenceLabel
            For display in reference box.
        """
        # Extract main display info
        ref_id = ref.get('ref_id')
        ref_title = ref.get('title')
        ref_author_list = ref.get('authors')
        ref_doi = ref.get('doi')
        ref_year = ref.get('year')
        if ref_year is None:
            ref_year = ref.get('date')

        if isinstance(ref_author_list, str):
            ref_author_list = ref_author_list.split('; ')

        # Format short and long author lists
        if ref_author_list is not None:
            ref_full_authors = '; '.join(ref_author_list)
            if len(ref_author_list) > 2:
                ref_first_authors = ref_author_list[0] + ', ' + ref_author_list[1] + ', et al.'
            else:
                ref_first_authors = ref_full_authors
        else:
            ref_first_authors = ''
            ref_full_authors = ''

        # Initialize indicator about whether reference is in library
        in_lib = 3

        # Build up strings with existing info
        # Small text is for abbreviated preview.
        # Expanded text is additional information for the larger
        # reference view when a label is clicked.
        ref_small_text = ''
        ref_expanded_text = ''
        if ref_id is not None:
            ref_small_text = ref_small_text + str(ref_id) + '. '
            ref_expanded_text = ref_expanded_text + str(ref_id) + '. '
        if ref_author_list is not None:
            ref_small_text = ref_small_text + ref_first_authors
            ref_expanded_text = ref_expanded_text + ref_full_authors
        if ref.get('publication') is not None:
            ref_expanded_text = ref_expanded_text + '\n' + ref.get('publication')
        if ref_year is not None:
            ref_small_text = ref_small_text + ', ' + ref_year
            ref_expanded_text = ref_expanded_text + ', ' + ref_year
        if ref_title is not None:
            ref_small_text = ref_small_text + ', ' + ref_title
            ref_expanded_text = ref_expanded_text + '\n' + ref_title
        if ref_doi is not None:
            ref_expanded_text = ref_expanded_text + '\n' + ref_doi
            try:
                doc_json = self.library.get_document(ref_doi, return_json=True)
                has_file = doc_json.get('file_attached')
                if has_file:
                    in_lib = 2
                else:
                    in_lib = 1
            except Exception:
                in_lib = 0

        # Cut off length of small text to fit within window
        ref_small_text = td(ref_small_text, 66)

        # Make ReferenceLabel object and set attributes
        ref_label = ReferenceEntryLabel(ref_small_text, self)
        ref_label.small_text = ref_small_text
        ref_label.expanded_text = ref_expanded_text
        ref_label.reference = ref
        ref_label.doi = ref.get('doi')
        ref_label.status = in_lib

        # Append all labels to reference text lists in in Data()
        self.data.small_ref_labels.append(ref_small_text)
        self.data.expanded_ref_labels.append(ref_expanded_text)

        return ref_label

    def remove_label(self, label):
        # index = self.ref_items_layout.indexOf(label)
        self.ref_items_layout.removeWidget(label)
        label.deleteLater()


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Internal Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def _reset_forms(self, next_id=True):
        if next_id:
            # Increment the reference ID by 1
            ref_num = self.ref_id_box.text()
            if ref_num is not None:
                number = int(ref_num)
                number += 1
                self.ref_id_box.setText(str(number))

        # Reset all other forms
        for textline in self.widget_list:
            textline.setText('')

    def _check_lib(self, doi=None):
        """
        Checks library for a DOI, returns true if found.

        Parameters
        ----------
        doi : str
            DOI of the paper to look up.

        Returns
        -------
        in_library: bool
            True if DOI is found in the user's library.
            False otherwise.
        """
        if doi is None:
            entered_doi = self.doc_selector.value
        else: entered_doi = doi

        if entered_doi == '':
            return False
        in_library = self.library.check_for_document(entered_doi)
        return in_library

    def _set_response_message(self, message):
        """
        Sets the line of text to indicate program status.
        """
        self.response_label.setText(message)
        self.response_label.repaint()
        qApp.processEvents()
        self.response_label.show()

    def _populate_data(self, info):
        """
        Sets attributes of Data object with information about the paper
        being searched for in the main text box.

        Parameters
        ----------
        info : PaperInfo object
            See pypub.paper_info
            Holds information about a paper.
        """
        self.data.entry = info.entry
        self.data.references = info.references
        self.data.doi = info.doi
        self.data.scraper_obj = info.scraper_obj
        self.data.pdf_link = info.pdf_link
        self.data.url = info.url
        self.data.small_ref_labels = []
        self.data.expanded_ref_labels = []


class LibraryInterface(object):

    @classmethod
    def create(self, library_type):
        """
        Creates instance of the user library

        Returns: UserLibrary object
        """
        if library_type == 'Mendeley':
            return MendeleyLibraryInterface()

        return None


class MendeleyLibraryInterface(LibraryInterface):
    
    def __init__(self):
        self.lib = client_library.UserLibrary()
        self.api = API()

    def sync(self):
        self.lib.sync()

    def check_for_document(self, doi=None, pmid=None):
        return self.lib.check_for_document(doi=doi, pmid=pmid)

    def get_document(self, doi, return_json=False):
        return self.lib.get_document(doi=doi, return_json=return_json)
    
    # def trash_document(self, doc_id):
    #     self.api.documents.move_to_trash(doc_id=doc_id)

    def trash_document(self, doi=None, url=None, pmid=None, fulltext=None):
        """
        Moves a paper from the user's library to trash
        (in Mendeley).

        Parameters
        ----------
        doi : str
            DOI of the paper to be deleted.
        """

        if doi is not None:

            # This is not wrapped in a try/except because the method calling
            # it implements the try/except.
            doc_json = self.lib.get_document(doi, return_json=True)

            if doc_json is None:
                raise DocNotFoundError

            doc_id = doc_json.get('id')

            self.api.documents.move_to_trash(doc_id=doc_id)

        # Catch any other case because URL and PMID searches are
        # not yet implemented at this time.
        else:
            raise UnsupportedEntryTypeError('Must provide a valid ID to move document to trash.'
                                             '\nURL and Pubmed ID is not yet supported.')

    def update_document(self, doc_id, notes):
        # This is used to add notes via a POST request
        self.api.documents.update(doc_id=doc_id, new_data=notes)

    def add_to_library(self, doi):
        self.lib.add_to_library(doi=doi)

    def get_file_content_from_doc_id(self, doc_id):
        file_content, file_name, file_id = self.api.files.get_file_content_from_doc_id(doc_id=doc_id)
        return file_content, file_name, file_id


class Data(object):
    def __init__(self):
        self.references = None
        self.entry = None
        self.doi = None
        self.scraper_obj = None
        self.url = None
        self.pdf_link = None
        self.doc_response_json = None
        self.small_ref_labels = []
        self.expanded_ref_labels = []

    def __repr__(self):
        return u'' + \
            'Title: %s' % self.entry.get('title') + \
            'Author: %s' % self.entry.get('authors') + \
            'DOI: %s' % self.doi


# This is meant to be a popup that appears when the GUI is launched
# to indicate that the library is being loaded. Not sure if this is
# necessary because the loading seems to happen quickly.
class LoadingPopUp(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(300, 100)
        message = QLabel('Loading Library...')
        message.setAlignment(Qt.AlignCenter)

        vbox = QVBoxLayout()
        vbox.addWidget(message)

        self.setLayout(vbox)

        _center(self)
        self.show()

    def close_window(self):
        qApp.quit()


class ClickFilter(QObject):
    """
    This is the eventFilter for ReferenceLabel. It handles the click
    events and emits either 'clicked' (for a single click) or 'doubleclicked'
    (for a double click) signals that can be assigned to functions.
    """
    clicked = pyqtSignal()
    doubleclicked = pyqtSignal()

    def __init__(self, widget):
        super(ClickFilter, self).__init__()
        self.parent = widget
        self.highlighting = False

        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self.set_highlighting)

        self.doubleclick_timer = QTimer()
        self.doubleclick_timer.setSingleShot(True)
        self.doubleclick_timer.timeout.connect(self.single_click)

    def eventFilter(self, widget, event):
        if event.type() == QEvent.MouseButtonPress:
            # Start timer to determine if the mouse is being held
            # down and the user is highlighting.
            self.click_timer.start(200)
        # If the user is clicking without highlighting, send
        # the 'clicked' signal.
        if event.type() == QEvent.MouseButtonRelease:
            self.click_timer.stop()
            if not self.highlighting:
                if self.doubleclick_timer.isActive():
                    if widget.rect().contains(event.pos()):
                        self.doubleclicked.emit()
                        self.doubleclick_timer.stop()
                        return True
                else:
                    self.doubleclick_timer.start(200)
            self.highlighting = False
        return False

    def set_highlighting(self):
        self.highlighting = True

    def single_click(self):
        self.clicked.emit()


# Centering the widget
# frameGeometry gets the size of the widget I'm making.
# QDesktopWidget finds the size of the screen
# The self.move moves my widget's top left corner to the coords of the
# top left corner of the centered qr frame.
def _center(widget):
    qr = widget.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    widget.move(qr.topLeft())


def _layout_widgets(layout):
    """
    Returns a list of all of the widget items in a given layout.
    Ignores spacer items.
    """
    all_widgets = []
    for i in range(layout.count()):
        item = layout.itemAt(i).widget()
        if type(item) is not QSpacerItem:
            all_widgets.append(item)
    return all_widgets


def _delete_all_widgets(layout):
    if type(layout.itemAt(0)) == QSpacerItem:
        startIndex = 1
    else:
        startIndex = 0
    while layout.count() > 1:
        item = layout.itemAt(startIndex).widget()
        layout.removeWidget(item)
        item.deleteLater()


def _copy_to_clipboard(text):
    clipboard = QApplication.clipboard()
    clipboard.setText(text)
    event = QEvent(QEvent.Clipboard)
    app.sendEvent(clipboard, event)


def _send_msg(message):
    QMessageBox.information(QMessageBox(), 'Information', message)


def _open_file(filename):
        # Platform-independent file opening calls
        if sys.platform == 'win32':
            os.startfile(filename)
        else:
            if sys.platform == 'darwin':
                opener = 'open'
            else:
                opener = 'xdg-open'
            subprocess.call([opener, filename])


if __name__ == '__main__':

    app = QApplication(sys.argv)

    main_window = QTabWidget()

    tab1 = QMainWindow()
    tab1.setCentralWidget(EntryWindow(parent_tab_window=main_window, encapsulating_window=tab1))
    menubar = tab1.menuBar()
    test_menu = menubar.addMenu("hello world")

    main_window.addTab(tab1, "Main")
    main_window.resize(800,700)
    _center(main_window)
    main_window.setWindowTitle('ScholarTools')

    second_tab = InternalSearchWindow(parent_tab_window=main_window, sibling_window=tab1)
    main_window.addTab(second_tab, "Library Search")

    # tab_bar = main_window.tabBar()
    # menu = QMenu()
    # menu.addAction("Hello")
    # menu.addAction("World")
    # menuButton = QToolButton()
    # menuButton.setArrowType(Qt.DownArrow)
    # menuButton.setMenu(menu)
    # tab_bar.setTabButton(0, QTabBar.RightSide, menuButton)

    main_window.show()

    # loading = LoadingPopUp()
    # entryWindow = EntryWindow()
    # loading.close()

    sys.exit(app.exec_())
