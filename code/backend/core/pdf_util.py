import pikepdf
import logging

def pdf_pw_check(tmp_file, generated_file_name):
    """
    Function to check if a PDF file is password protected
    args -
    tmp_file - temporary file
    generated_file_name - name of the file
    returns -
    error_message - error message if file is password protected
    """
    error_message = None
    try:
        pdf = pikepdf.open(tmp_file)
    except pikepdf.PasswordError as e:
        logging.error('Runtime error: ', e)
        logging.error(f'{generated_file_name} is Password protected!')
        error_message = 'File is Password Protected'
    except Exception as e:
        logging.error('Runtime error: ', e)
        logging.error(f'{generated_file_name} error reading file!')
        error_message = 'Error reading file'
    return error_message