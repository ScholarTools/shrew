# Shrew  
A GUI interface for Scholar Tools

## Overview  
Shrew provides a suite of tools allowing a greater degree of interaction with a library of academic papers. Once connected with your Mendeley library, Shrew allows you to quickly add papers to it, get reference information about papers both with and without your library (including information about which referencing papers already exist in your library), comment between papers, and more. The paper and reference retrieval is handled via Pubmed and individual publisher websites. A local database of paper information, references, and authors is made using SQLite.

## Setup  
This repository is primarily a GUI wrapper for functionality found within other ScholarTools repositories. To use Shrew, follow the download instructions at [python_tools](https://github.com/ScholarTools/python_tools). It is recommended to download all repositories, but at a minimum, you will need `mendeley_python`, `reference_resolver`, `pypub`, and `pdfetch`, along with Shrew.

Currently, this system is compatible only with Mendeley. Shrew works with the user and library information provided to `mendeley_python`, so to begin using it, you must enter valid Mendeley account information. 

Within the `mendeley` directory in `mendeley_python`, copy the `config_template.py` file. Enter the user information into the attributes of the `DefaultUser` class, and then rename the file `user_config.py`.

Shrew is able to be used by running the `gui.py` file within `shrew`. 

## Main Window Functions  
#### Description of Main window functions
* Enter information for a single paper within the text line, and select the corresponding radio button below. At this time, only DOIs are supported.  
* The indicator to the left of the text line shows the status of the paper in your library.
  * Red - paper is not found in your library.
  * Orange - a document with descriptive information (i.e. title, authors, DOI, etc.) is in your library, but has no file attached.
  * Green - a document with a file attached is in your library.
* Sync with Library
  * Syncs the information the GUI window has about your library with up-to-date information from Mendeley. Most other functions handle this automatically, but may be useful for updating paper status information.
* Get References
  * Get the references for the DOI entered in the text box (if valid). References will be displayed as individual labels below, in the main body of the window.
* Open Notes
  * Open a separate, editable window with the notes on the entered paper from Mendeley. This window also contains the abstract of the paper (if available) and descriptive data (i.e. authors, journal name, etc.)
* Add to Library
  * Add the paper with the entered DOI to your Mendeley library and local database.
* Move to Trash
  * Move the paper from your Mendeley library into the trash. Does not delete information from the local database.
* Follow Refs Forward
  * Displays all papers *in your library* that cite the entered paper. This list is not exhaustive, and is limited only to your library.
* History dropdown menu
  * DOIs you enter in the textbox and interact with are added here for quick reference.
* Enter References
  * Manually enter the reference list for a paper. This may be useful for entering a paper for which references could not be automatically retrieved.
* Add All References
  * Attempt to add every paper from the reference section of the entered paper to your library.
* Resolve DOIs to References
  * Attempt to automatically match each paper in the entered paper's reference list with its DOI. Also performs a check to determine if each paper is in your library.

#### Description of Library Search window functions  
* This window is for searching within your library. Search looks for the search terms anywhere within those fields, and are case-insensitive. For example, a search for "neuro" in the Title field will return all papers with "neuro" anywhere in the title, including as part of a longer word. Similarly, a search for "199" in the Year field will return all papers within 1990-1999.

#### Description of reference label functions
* Each reference label shows a preview of the first two authors, the publication year, and an abbreviated title. Clicking once on a label expands it so that the journal name, full author list, and full title are visible.
* Double clicking a label opens the notes/abstract/descriptive information window for that paper.
* There are right-click options on each label that are the same as the Main window buttons. 

## Troubleshooting
* Opening Shrew or syncing with the library fails with an HTTP status code 403.
  * If using Mendeley, the developent token may have expired. This is necessary because Shrew uses a non-production endpoint. To generate a new development token, go to [https://development-tokens.mendeley.com](https://development-tokens.mendeley.com), and input the new token into the `user_config.py` file.