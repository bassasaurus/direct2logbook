def check_float(field):

    return field


def check_text(field):

    return field


def check_date(field):

    return field


def format_route(string):

    new_string = string.replace(' ', '-').upper()

    if new_string.endswith('-'):
        new_string = new_string[:-1]

    return new_string


def assign_ils(row_id):
    if row_id > 0:
        return 'ILS'
    else:
        return ''


def convertBool(row_id):

    if float(row_id) > 0:
        return True
    else:
        return False
