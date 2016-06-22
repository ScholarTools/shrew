# Standard
import sys

# Third-party
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

# Local
from mendeley import client_library
from mendeley.api import API
import reference_resolver as rr
from pypub.utils import get_truncated_display_string as td
from error_logging import log

from mendeley.errors import *
from pypub_errors import *


class Window(QWidget):
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
     - Possibly make the window tabbed with expanded functionality?
     - Implement reading the abstract of any paper

    """
    def __init__(self):
        super().__init__()
        #loading = LoadingPopUp()
        self.library = self._instantiate_library()
        self.api = API()
        #loading.close_window()

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.initUI()
        self.data = Data()

    def initUI(self):

        # Make all widgets
        self.entryLabel = QLabel('Please enter a DOI')
        self.indicator = QPushButton()
        self.textEntry = QLineEdit()
        self.doi_check = QRadioButton('DOI')
        self.doi_check.setChecked(True)
        self.url_check = QRadioButton('URL')
        self.refresh = QPushButton('Sync with Library')
        self.get_references = QPushButton('Get References')
        self.open_notes = QPushButton('Open Notes')
        self.add_to_lib = QPushButton('Add to Library')
        self.stacked_responses = QStackedWidget()
        self.ref_area = QScrollArea()
        self.get_all_refs = QPushButton('Add All References')

        # Set connections to functions
        self.textEntry.textChanged.connect(self.update_indicator)
        self.textEntry.returnPressed.connect(self.get_refs)
        self.get_references.clicked.connect(self.get_refs)
        self.open_notes.clicked.connect(self.show_main_notes_box)
        self.add_to_lib.clicked.connect(self.add_to_library_from_main)
        self.get_all_refs.clicked.connect(self.add_all_refs)
        self.refresh.clicked.connect(self.resync)

        # Format indicator button
        self.indicator.setStyleSheet("background-color: rgba(0,0,0,0.25);")
        self.indicator.setAutoFillBackground(True)
        self.indicator.setFixedSize(20,20)
        self.indicator.setToolTip("Green if DOI found in library")

        # Set bool to keep track of if a DOI is in the library
        self.is_in_lib = False

        # TODO: Make this ToolTip color work
        self.setStyleSheet("""QToolTip {
                                    background-color: white;
                                    color: black;
                                    border: black solid 1px;
                                    }""")

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
        #checkboxes.addWidget(self.doi_check)
        #checkboxes.addWidget(self.url_check)
        checkboxes.addWidget(self.refresh)
        checkboxes.addWidget(self.get_references)
        checkboxes.addWidget(self.open_notes)
        checkboxes.addWidget(self.add_to_lib)
        checkboxes.addStretch(1)

        # Create a horizontal box for indicator and textEntry
        textline = QHBoxLayout()
        textline.addWidget(self.indicator)
        textline.addWidget(self.textEntry)

        # Create a vertical box layout.
        # Populate with widgets and add stretch space at the bottom.
        self.vbox = QVBoxLayout()
        self.vbox.addWidget(self.entryLabel)
        self.vbox.addLayout(textline)
        self.vbox.addLayout(checkboxes)
        self.vbox.addWidget(self.stacked_responses)
        self.vbox.addWidget(self.ref_area)
        self.vbox.addWidget(self.get_all_refs)
        self.vbox.addStretch(1)

        # Set layout to be the vertical box.
        self.setLayout(self.vbox)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        # Sizing, centering, and showing
        self.resize(500,600)
        _center(self)
        self.setWindowTitle('ScholarTools')
        self.show()

    # +=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+= Start of Functions

    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Main Window Button Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def update_indicator(self):
        """
        Updates indicator button color if the DOI in the text field is in user's library.
        """
        in_library = self._check_lib()
        if in_library:
            self.data.doc_response_json = self.library.get_document(self._get_doi(), return_json=True)
            print(self.data.doc_response_json.keys())
            self.indicator.setStyleSheet("background-color: rgba(0, 255, 0, 0.25);")
            self.is_in_lib = True

        else:
            self.data.doc_response_json = None
            self.indicator.setStyleSheet("background-color: rgba(255, 0, 0, 0.25);")
            self.is_in_lib = False

    def resync(self):
        self.library.sync()
        if self.ref_items_layout.count() > 1:
            for x in range(1, self.ref_items_layout.count()):
                label = self.ref_items_layout.itemAt(x).widget()
                doi = label.doi
                if doi is not None:
                    exists = self.library.check_for_document(doi)
                    if exists:
                        label.setStyleSheet("background-color: rgba(0,255,0,0.25);")
                    else:
                        label.setStyleSheet("background-color: rgba(255,0,0,0.25);")
        self.update_indicator()


    def get_refs(self):
        """
        Gets references for paper corresponding to the DOI in text field.
        Displays reference information in scrollable area.
        """
        self.stacked_responses.hide()

        # Get DOI from text field and handle blank entry
        entered_doi = self._get_doi()
        self._populate_response_widget()

        if entered_doi == '':
            self.stacked_responses.setCurrentIndex(0)
            self.stacked_responses.show()
            return

        # Resolve DOI and get references
        try:
            paper_info = rr.resolve_doi(entered_doi)
            refs = paper_info.references
            self._populate_data(paper_info)
        except UnsupportedPublisherError as exc:
            log(method='gui.Window.get_refs', message='Unsupported Publisher', error=str(exc), doi=entered_doi)
            QMessageBox.warning(self, 'Warning', 'Unsupported Publisher')
            return
        except ParseException or AttributeError as exc:
            log(method='gui.Window.get_refs', message='Error parsing journal page', error=str(exc), doi=entered_doi)
            QMessageBox.warning(self, 'Warning', 'Error parsing journal page')
            return
        except Exception as exc:
            log(method='gui.Window.get_refs', error=str(exc), doi=entered_doi)
            QMessageBox.warning(self, 'Warning', str(exc))

        # First clean up existing GUI window.
        # If there are widgets in the layout (i.e. from the last call to 'get_refs'),
        # delete all of those reference labels before adding more.
        _delete_all_widgets(self.ref_items_layout)

        for ref in refs:
            ref_label = self.ref_to_label(ref)
            self.ref_items_layout.insertWidget(self.ref_area_layout.count() - 1, ref_label)

        self.ref_area.show()

    #
    # For "Open Notes", see "Notes Box Display Functions" section below.
    #

    def add_to_library_from_main(self):
        """
        Adds paper corresponding to the DOI in the text field to the user library,
        if it is not already there.
        """
        if self.is_in_lib:
            QMessageBox.information(self, 'Information', 'Paper is already in library.')
            return

        doi = self._get_doi()

        try:
            self.library.add_to_library(doi)
        except UnsupportedPublisherError as exc:
            log(method='gui.Window.add_to_library_from_main', message='Unsupported publisher', error=str(exc), doi=doi)
            QMessageBox.warning(self, 'Warning', 'Publisher is not yet supported.\n'
                                                 'Document not added.')
            return
        except CallFailedException as call:
            log(method='gui.Window.add_to_library_from_main', message='Call failed', error=str(call), doi=doi)
            QMessageBox.warning(self, 'Warning', str(call))
        except ParseException or AttributeError as exc:
            log(method='gui.Window.add_to_library_from_main', message='Error while parsing article webpage',
                error=str(exc), doi=doi)
            QMessageBox.warning(self, 'Warning', 'Error while parsing article webpage.')
        except Exception as exc:
            log(method='gui.Window.add_to_library_from_main', error=str(exc), doi=doi)
            QMessageBox.warning(self, 'Warning', str(exc))
        self._update_document_status(doi, adding=True)
        self.update_indicator()

    def add_all_refs(self):
        """
        Attempts to add every reference from the paper corresponding
        to the DOI in the text field to the user's library.
        """
        # The ref_items_layout would hold the ref_labels.
        # If count is 0, none are listed, and it needs to be populated.
        if self.ref_items_layout.count() == 1:
            self.get_refs()

        main_doi = self._get_doi()

        for x in range(1, self.ref_items_layout.count()):
            label = self.ref_items_layout.itemAt(x).widget()
            doi = label.doi
            print(label.small_text)
            self.add_to_library_from_label(label, doi, index=x, referencing_paper=main_doi, popups=False)


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

        # Format short and long author lists
        if ref_author_list is not None:
            ref_full_authors = '; '.join(ref_author_list)
            if len(ref_author_list) > 2:
                ref_first_authors = ref_author_list[0] + ', ' + ref_author_list[1] + ', et al.'
            else:
                ref_first_authors = ref_full_authors

        # Initialize indicator about whether reference is in library
        in_lib = 2

        # Build up strings with existing info
        # Small text is for abbreviated preview.
        # Expanded text is additional information for the larger
        # reference view when a label is clicked.
        ref_small_text = ''
        ref_expanded_text = ''
        if ref_id is not None:
            ref_small_text = ref_small_text + str(ref_id)
            ref_expanded_text = ref_expanded_text + str(ref_id)
        if ref_author_list is not None:
            ref_small_text = ref_small_text + '. ' + ref_first_authors
            ref_expanded_text = ref_expanded_text + '. ' + ref_full_authors
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
            in_library = self.library.check_for_document(ref_doi)
            if in_library:
                in_lib = 1
            else:
                in_lib = 0

        # Cut off length of small text to fit within window
        ref_small_text = td(ref_small_text, 66)

        # Make ReferenceLabel object and set attributes
        ref_label = ReferenceLabel(ref_small_text, self)
        ref_label.small_text = ref_small_text
        ref_label.expanded_text = ref_expanded_text
        ref_label.reference = ref
        ref_label.doi = ref.get('doi')

        # Connect click to expanding the label
        # Connect double click to opening notes/info window
        ref_label.ClickFilter.clicked.connect(self.change_ref_label)
        ref_label.ClickFilter.doubleclicked.connect(self.show_ref_notes_box)

        # Append all labels to reference text lists in in Data()
        self.data.small_ref_labels.append(ref_small_text)
        self.data.expanded_ref_labels.append(ref_expanded_text)

        # Make widget background color green if document is in library.
        # Red if not in library.
        # Neutral if there is no DOI
        if in_lib == 1:
            ref_label.setStyleSheet("background-color: rgba(0,255,0,0.25);")
        elif in_lib == 0:
            ref_label.setStyleSheet("background-color: rgba(255,0,0,0.25);")

        return ref_label

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


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Reference Label Right-Click Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def add_to_library_from_label(self, label, doi, index=None, referencing_paper=None, popups=True):
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
                QMessageBox.warning(self, 'Warning', 'No DOI found for this reference')
            return

        # Check that the paper isn't already in the user's library
        if self._check_lib(doi):
            if popups:
                QMessageBox.information(self, 'Information', 'Paper is already in library.')
            return

        # Try to add, have separate windows for each possible error
        try:
            self.library.add_to_library(doi)
        except UnsupportedPublisherError as exc:
            log(method='gui.Window.add_to_library_from_label', message='Publisher unsupported', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                QMessageBox.warning(self, 'Warning', 'Publisher is not yet supported.\n'
                                    'Document not added.')
            return
        except CallFailedException as call:
            log(method='gui.Window.add_to_library_from_label', message='Call failed', error=str(call), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                QMessageBox.warning(self, 'Warning', str(call))
            return
        except ParseException as exc:
            log(method='gui.Window.add_to_library_from_label', message='Error parsing webpage', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                QMessageBox.warning(self, 'Warning', str(exc))
        except TypeError or AttributeError as exc:
            log(method='gui.Window.add_to_library_from_label', message='Error parsing webpage', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                QMessageBox.warning(self, 'Warning', 'Error parsing page.')
        except Exception as exc:
            log(method='gui.Window.add_to_library_from_label', error=str(exc), doi=doi,
                ref_index=index, main_lookup=referencing_paper)
            if popups:
                QMessageBox.warning(self, 'Warning', str(exc))
        self._update_document_status(doi, label=label, adding=True, popups=popups)

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
            QMessageBox.warning(self, 'Warning', 'No DOI found for this reference')
            return
        self.textEntry.setText(doi)
        self.get_refs()

    def move_doc_to_trash(self, doi=None, label=None):
        """
        Moves a paper from the user's library to trash
        (in Mendeley).
        Either doi or label must be supplied.

        Parameters
        ----------
        doi : str
            DOI of the paper to be deleted.
        label : ReferenceLabel
            If this was used from right-clicking a label,
            this is the clicked label.
        """
        if doi is None:
            if label is None:
                raise LookupError('Must provide either a DOI or label to move_doc_to_trash.')
            doi = label.doi
        doc_json = self.library.get_document(doi, return_json=True)
        if doc_json is None:
            QMessageBox.information(self, 'Information', 'Document is not in your library.')
            return
        doc_id = doc_json.get('id')
        self.api.documents.move_to_trash(doc_id)
        self._update_document_status(doi, label=label)


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Notes Box Display Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def show_main_notes_box(self):
        """
        Displays the notes/info window for the paper from the DOI in
        the main text box.
        """
        # Paper must be in the library to display the window
        if not self.is_in_lib:
            QMessageBox.information(self, 'Information', 'Document not found in library.')
            return
        doc_json = self.data.doc_response_json
        if doc_json is None:
            raise LookupError('Main document JSON not found')
        notes = doc_json.get('notes')
        self.tnw = TabbedNotesWindow(parent=self, notes=notes, doc_json=doc_json)
        self.tnw.show()

    def show_ref_notes_box(self):
        """
        Displays the notes/info window for a paper double-clicked
        from the references window.
        """
        label = self.sender().parent
        try:
            doc_response_json = self.library.get_document(label.doi, return_json=True)
        except DOINotFoundError:
            reply = QMessageBox.question(self,'Message', 'Document not found in library.\nWould you like to add it?',
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.add_to_library_from_label(label, label.doi)
                return
            else:
                return
        notes = doc_response_json.get('notes')
        self.tnw = NotesWindow(parent=self, notes=notes, doc_json=doc_response_json)
        self.tnw.show()


    # ++++++++++++++++++++++++++++++++++++++++++++
    # ============================================ Internal Functions
    # ++++++++++++++++++++++++++++++++++++++++++++
    def _instantiate_library(self):
        """
        Creates instance of the user library

        Returns: UserLibrary object
        """
        return client_library.UserLibrary()

    def _get_doi(self):
        """
        Gets DOI from main text box if DOI button is selected.

        Right now, the URL option is not supported. To do this I'll
        need to implement link_to_doi and resolve_link in reference_resolver.
        """
        text = self.textEntry.text()

        if self.doi_check.isChecked():
            return text
        else:
            return text

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
            entered_doi = self._get_doi()
        else: entered_doi = doi

        self._populate_response_widget()

        if entered_doi == '':
            return False
        in_library = self.library.check_for_document(entered_doi)
        return in_library

    def _populate_response_widget(self):
        """
        Adds label widgets to hidden widget.
        Only appears if a function is used without entering text.
        """
        if self.stacked_responses.count() < 3:
            self.stacked_responses.addWidget(QLabel('Please enter text above.'))
            self.stacked_responses.addWidget(QLabel('Found in library!'))
            self.stacked_responses.addWidget(QLabel('Not found in library.'))
            self.stacked_responses.hide()

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
        self.data.idnum = info.idnum
        self.data.pdf_link = info.pdf_link
        self.data.url = info.url
        self.data.small_ref_labels = []
        self.data.expanded_ref_labels = []

    def _update_document_status(self, doi, label=None, adding=False, popups=True):
        """
        Updates the indicators about whether a certain paper is in the user's library.
        If from a reference label, change color of that label.
        If from the main window, change color of indicator.

        Parameters
        ----------
        doi : str
            DOI of the paper to check for.
        label : ReferenceLabel
            Reference label of the paper in question (if being updated
            from the references box)
        adding : bool
            Indicates whether a paper is being added or deleted.
        """
        self.library.sync()
        exists = self.library.check_for_document(doi)
        if exists:
            doc_json = self.library.get_document(doi, return_json=True)
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
                    delete_button.clicked.connect(lambda: self.move_doc_to_trash(doi=doi))
                    msgBox.addButton(QPushButton('Ignore'), QMessageBox.AcceptRole)

                    reply = msgBox.exec_()

                    print(reply)

                    # If the user chose to delete, exit this function.
                    if reply != QMessageBox.Accepted:
                        return

            if label is not None:
                label.setStyleSheet("background-color: rgba(0,255,0,0.25);")
            else:
                self.is_in_lib = True
        else:
            if adding:
                if popups:
                    QMessageBox.warning(self, 'Warning', 'An error occurred during sync.\n'
                                        'Document may not have been added.')
            if label is not None:
                label.setStyleSheet("background-color: rgba(255,0,0,0.25);")
            else:
                self.update_indicator()


class NotesWindow(QWidget):
    """
    This is the smaller window that appears displaying notes for a given reference.

    --- Features ---
    * Text box: Displays the current notes saved for a given document, and allows
       for editing.
    * Save button: Saves the changes made to the notes, and syncs with Mendeley.
    * Save and Close button: Saves the changes made to the notes, syncs, with
       Mendeley, and closes the notes window.
    * Prompting before exit: If the user attempts to close the window after
       making unsaved changes to the notes, a pop-up window appears asking
       to confirm the action without saving. Provides an option to save.

    TODOs:
     - Fix the prompt before exit (currently appears when closing the main
        window, even after the notes window is gone. Maybe this has to do
        with having closed the window but not terminating the widget process?)
     - Add informative window title to keep track of which paper is being
        commented on.
     - Add (automatic or voluntary) feature to input a little note saying something
        like "edited with reference to [original file that references this one]"

    """
    def __init__(self, parent=None, notes=None, doc_json=None):
        super(NotesWindow, self).__init__()
        self.parent = parent
        self.notes = notes
        self.doi = None
        self.doc_id = None
        self.caption = None

        if doc_json is not None:
            self.doi = doc_json.get('doi')
            self.doc_id = doc_json.get('id')
            self.make_captions(doc_json)

        self.initUI()

    def initUI(self):
        # Make widgets
        self.notes_title = QLabel('Notes:')
        self.notes_box = QTextEdit()
        self.save_button = QPushButton('Save')
        self.save_and_close_button = QPushButton('Save and Close')
        self.saved_indicator = QLabel('Saved!')
        self.saved_indicator.hide()

        # Connect widgets
        self.save_button.clicked.connect(self.save)
        self.save_and_close_button.clicked.connect(self.save_and_close)
        self.notes_box.textChanged.connect(self.updated_text)

        if self.notes is not None:
            self.notes_box.setText(self.notes)

        self.saved = True

        hbox = QHBoxLayout()
        hbox.addWidget(self.save_button)
        hbox.addWidget(self.save_and_close_button)

        # Make layout and add widgets
        vbox = QVBoxLayout()
        vbox.addWidget(self.notes_title)
        vbox.addWidget(self.notes_box)
        vbox.addWidget(self.saved_indicator)
        vbox.addStretch(1)

        vbox.addLayout(hbox)

        self.setLayout(vbox)

        # Connect keyboard shortcut
        self.close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.close_shortcut.activated.connect(self.close)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.setWindowTitle(self.caption)
        self.show()

    def make_captions(self, doc_json):
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

        self.caption = ''

        if doc_year is not None and doc_authors is not None:
            self.caption = first_authors + ' (' + str(doc_year) + ')'
        elif doc_title is not None:
            self.caption = doc_title
        else:
            self.caption = self.doi


    def save(self):
        updated_notes = self.notes_box.toPlainText()
        notes_dict = {"notes" : updated_notes}
        self.parent.api.documents.update(self.doc_id, notes_dict)
        self.parent.library.sync()
        self.saved = True

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
    def __init__(self, parent=None, notes=None, doc_json=None):
        super(TabbedNotesWindow, self).__init__()
        self.parent = parent
        self.notes = notes
        self.doc_json = doc_json
        self.doi = None
        self.doc_id = None
        self.caption = None

        if self.doc_json is not None:
            self.doi = self.doc_json.get('doi')
            self.doc_id = self.doc_json.get('id')
            self.make_captions(self.doc_json)

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

        #self.initUI()

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

    def make_captions(self, doc_json):
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
        self.parent.api.documents.update(self.doc_id, notes_dict)
        self.parent.library.sync()

        # Update local version of notes to updated version and indicate saved
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

        self.metrics = QFontMetrics(self.font())
        elided = self.metrics.elidedText(text, Qt.ElideRight, self.width())

        self.setText(text)
        self.expanded_text = None
        self.small_text = None
        self.reference = None
        self.doi = None

        self.ClickFilter = ClickFilter(self)
        self.installEventFilter(self.ClickFilter)

        # Connect copy to clipboard shortcut
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(_copy_to_clipboard)

        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setWordWrap(True)

    def contextMenuEvent(self, QContextMenuEvent):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #d9d9d9; }")

        add_to_lib = menu.addAction("Add to library")
        ref_lookup = menu.addAction("Look up references")
        move_to_trash = menu.addAction("Move to trash")
        action = menu.exec_(self.mapToGlobal(QContextMenuEvent.pos()))
        if action == add_to_lib:
            self.parent.add_to_library_from_label(self, self.reference.get('doi'))
        elif action == ref_lookup:
            self.parent.lookup_ref(self.reference.get('doi'))
        elif action == move_to_trash:
            self.parent.move_doc_to_trash(label=self)


# This is meant to be a popup that appears when the GUI is launched
# to indicate that the library is being loaded. Not sure if this is
# necessary because the loading seems to happen quickly.
class LoadingPopUp(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(300, 100)
        message = QLabel('Loading Library...', self)
        message.move(50, 150)
        _center(self)
        self.show()

    def close_window(self):
        qApp.quit()


class Data(object):
    def __init__(self):
        self.references = None
        self.entry = None
        self.doi = None
        self.idnum = None
        self.scraper_obj = None
        self.url = None
        self.pdf_link = None
        self.doc_response_json = None
        self.small_ref_labels = []
        self.expanded_ref_labels = []


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

def _copy_to_clipboard():
    clipboard = QApplication.clipboard()
    #clipboard.setText()
    event = QEvent(QEvent.Clipboard)
    app.sendEvent(clipboard, event)


if __name__ == '__main__':

    app = QApplication(sys.argv)

    w = Window()
    #nw = NotesWindow()
    #l = LoadingPopUp()

    sys.exit(app.exec_())