from flights.models import Flight, Total
from django.contrib.auth.decorators import login_required
import datetime
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, legal, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, SimpleDocTemplate, Spacer, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from django.core.mail import EmailMessage
from django.core.mail import send_mail

from django.http import HttpResponse
from django.template.response import TemplateResponse

def entry(object, flight):
    if not object:
        entry = '-'
    elif object == True:
        entry = str(flight.duration)
    else:
        entry = str(object)
    return entry


@login_required
def PDFView(request, user_id):

    user = request.user

    # flight_objects = Flight.objects.filter(user=user).order_by('date')
    flight_objects = Flight.objects.filter(user=user).order_by('-date')[:100]
    total_objects = Total.objects.filter(user=user)
    # number of flights per page
    # pages = Paginator(objects, 30)
    # Create the HttpResponse object with the appropriate PDF headers.
    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer,
                            pagesize=landscape(legal),
                            verbosity=1,
                            rightMargin=0.5*inch,
                            leftMargin=0.5*inch,
                            topMargin=0.5*inch,
                            bottomMargin=.25*inch)

    styles = getSampleStyleSheet()

    spacer = Spacer(1, 0.25*inch)

    tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
                        ])

    story = []

    #summary page starts here

    totals_that_exist =[]
    for total in total_objects:
        if total.total_time > 0.0:
            totals_that_exist.append(str(total.total))

    total_data = []
    for total in totals_that_exist:
        total = Total.objects.get(total=total)
        row = [str(total.total), str(total.total_time), str(total.pilot_in_command), str(total.second_in_command), str(total.cross_country),
                str(total.instructor), str(total.dual), str(total.solo), str(total.instrument), str(total.night), str(total.simulated_instrument),
                str(total.simulator), str(total.landings_day), str(total.landings_night), str(total.landings_day + total.landings_night)]

        total_data.append(row)

    total_header = [ "", "Time", "PIC", "SIC", "XC", "CFI", "Dual", "Solo", "IFR", "Night", "Hood", "Sim", "D Ldg", "N Ldg", "Total Ldg"]

    total_data.insert(0, total_header)

    total_table = Table(total_data)

    total_table.setStyle(tablestyle)

    story.append(total_table)

    story.append(spacer)

    # logbook starts here

    logbook_data = []

    logbook_header = ['Date', 'Type', 'Reg', 'Route', 'Block', 'PIC', 'SIC', 'XC', 'Night', 'IFR', 'Appr', 'Hold', 'D Ldg', 'N Ldg', 'Hood', 'CFI', 'Dual', 'Solo', 'Sim' ]

    for flight in flight_objects:

        date = flight.date
        Date = date.strftime("%m/%d/%Y")

        PIC = entry(flight.pilot_in_command, flight)
        SIC = entry(flight.second_in_command, flight)
        XC = entry(flight.cross_country, flight)
        Night = entry(flight.night, flight)
        IFR = entry(flight.instrument, flight)
        CFI = entry(flight.instructor, flight)
        Dual = entry(flight.dual, flight)
        Solo = entry(flight.solo, flight)
        Sim = entry(flight.simulator, flight)
        Day_LDG = entry(flight.landings_day, flight)
        Night_LDG = entry(flight.landings_night, flight)
        Hood = entry(flight.simulated_instrument, flight)

        appr = ''
        for approach in flight.approach_set.all():
            appr = appr + str(approach) + '-' + str(approach.number) + ' '

        hold = ''
        for holding in flight.holding_set.all():
            if holding.hold == True:
                hold = 'Yes'
            else:
                hold = '-'

        row = [Date, str(flight.aircraft_type), str(flight.registration), str(flight.route), str(flight.duration), PIC, SIC, XC, Night, IFR, appr, hold, Day_LDG, Night_LDG, Hood, CFI, Dual, Solo, Sim]

        logbook_data.append(row)

    logbook_data.insert(0, logbook_header)

    logbook_table = Table(logbook_data, repeatRows=(1))

    logbook_table.setStyle(tablestyle)

    styles = getSampleStyleSheet()

    story.append(logbook_table)



    #build pdf
    doc.build(story)
    # Get the value of the BytesIO buffer and write it to the response.
    pdf = buffer.getvalue()
    buffer.close()

    #email message/attachment
    # subject = "Logbook for {} {}".format(user.first_name, user.last_name)
    # user_email = user.email
    # email = EmailMessage(
    # subject,
    # 'Good luck on your interview!',
    # 'noreply@direct2logbook.com',
    # [user_email],
    # reply_to=['noreply@direct2logbook.com'],
    # headers={'Message-ID': 'logbook'},
    # )
    # email.attach('Logbook.pdf', pdf, 'application/pdf')
    # email.send()


    # template = TemplateResponse(request, 'pdf_output/waiting.html',)
    # return template


    #for testing
    response = HttpResponse('Check your email', content_type='application/pdf')
    response.write(pdf)
    return response
