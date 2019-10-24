
import csv
import io
import datetime
from flights.models import Flight, Aircraft, Approach, TailNumber
from dateutil.parser import parse


def csv_inspect(request):

    user = request.user

    file = request.FILES['file']

    decoded_file = file.read().decode('utf-8')

    io_string = io.StringIO(decoded_file)
    next(io_string)  # skips header row

    file = csv.reader(io_string, delimiter=',')

    memory_string = io.StringIO()

    for row in file:
        memory_string.write(str(row[0]))
        memory_string.write(str(row[1]))

    converted_file = csv.reader(memory_string, delimiter=',')

    for row in converted_file:
        print(row)

    return(file)
