import os
import inspect
import datetime


def log(message=None, method=None, error=None, doi=None, ref_index=None, main_lookup=None):
    filename = get_path()

    # Create timestamp for the error
    timestamp = '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())

    # If coming from a label, construct the reference to original paper
    if ref_index is not None and main_lookup is not None:
        ref_info = 'Reference number %i of paper with doi %s' % (ref_index, main_lookup)
    else:
        ref_info = None

    # Construct the full error log message as CSV line
    message_parts = [timestamp, method, message, error, doi, ref_info]
    error_log = ', '.join(part for part in message_parts if part is not None)
    error_log = error_log + '\n\n'

    #print(error_log)

    with open(filename, 'a') as file:
        file.write(error_log)


def get_path():
    current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    filename = current_dir + '/logfile.txt'
    return filename
