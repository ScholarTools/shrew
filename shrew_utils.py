def get_truncated_display_string(input_string,max_length = 50):
    if input_string is None:
        return None
    elif len(input_string) > max_length:
        return str(input_string[:max_length]) + '...'
    else:
        return input_string