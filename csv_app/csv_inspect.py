import csv
import io


def format_route(field):

    return field


def check_float(field):

    return field


def check_text(field):

    return field


def check_date(field):

    return field


def csv_inspect(file):

    new_file = io.StringIO()
    writer = csv.writer(new_file)

    for row in file:
        writer.writerow([
            str(row[0]),  # date
            str(row[1]),  # type
            str(row[2]),  # reg
            str(row[3]),  # route
            str(row[4]),  # duration
            str(row[5]),  # pic
            str(row[6]),  # sic
            str(row[7]),  # xc
            str(row[8]),  # night
            str(row[9]),  # ifr
            str(row[10]),  # appr
            str(row[11]),  # day ldg
            str(row[12]),  # night ldg
            str(row[13]),  # sim inst
            str(row[14]),  # cfi
            str(row[15]),  # dual
            str(row[16]),  # solo
            str(row[17]),  # sim
            str(row[18]),  # remarks
        ])

    new_file.seek(0, 0)  # gives reader a place to start

    return(new_file)
