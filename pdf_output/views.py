from flights.models import Flight, Total, Stat
from django.contrib.auth.decorators import login_required
import datetime
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, legal, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, SimpleDocTemplate, Spacer, TableStyle, PageBreak
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

class FooterCanvas(canvas.Canvas):

    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_canvas(page_count)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_canvas(self, page_count):
        page = "Page %s of %s" % (self._pageNumber, page_count)
        x = 130
        self.saveState()
        self.setFont('Helvetica', 10)
        self.drawString(45, 65, "I certify that the entries in this logbook are true.")

        self.setStrokeColorRGB(0, 0, 0)
        self.setLineWidth(0.5)
        self.line(255, 60, 480, 60)

        self.drawString(13*inch/2, 30, page)
        self.restoreState()

@login_required
def PDFView(request, user_id):

    user = request.user

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer,
                            pagesize=landscape(legal),
                            verbosity=1,
                            leftMargin=0.5*inch,
                            rightMargin=0.5*inch,
                            topMargin=0.5*inch,
                            bottomMargin=1.25*inch)

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


    text = "<para size=15 align=left><u><b>Category Class Summary</b></u></para>"
    cat_class_title = Paragraph(text, style=styles["Normal"])
    story.append(cat_class_title)
    story.append(spacer)

    #total table
    total_objects = Total.objects.filter(user=user)
    totals_that_exist =[]
    for total in total_objects:
        if total.total_time > 0.0:
            totals_that_exist.append(str(total.total))

    total_data = []
    for total in totals_that_exist:
        total = Total.objects.get(total=total)
        row = [str(total.total), str(total.total_time), str(total.pilot_in_command), str(total.second_in_command), str(total.cross_country),
                str(total.instructor), str(total.dual), str(total.solo), str(total.instrument), str(total.night), str(total.simulated_instrument),
                str(total.simulator), str(total.landings_day), str(total.landings_night), str(total.landings_day + total.landings_night),
                str(total.last_flown.strftime("%m/%d/%Y")), str(total.last_30), str(total.last_60), str(total.last_90), str(total.last_180),
                str(total.last_yr), str(total.last_2yr), str(total.ytd) ]

        total_data.append(row)

    total_header = [ "Cat/Class", "Time", "PIC", "SIC", "XC", "CFI", "Dual", "Solo",
                    "IFR", "Night", "Hood", "Sim", "D Ldg", "N Ldg", "Total Ldg",
                    "Last Flown", "30", "60", "90", "6mo", "1yr", "2yr", "Ytd"]

    total_data.insert(0, total_header)

    total_table = Table(total_data, hAlign='LEFT')

    total_table.setStyle(tablestyle)

    story.append(total_table)

    story.append(spacer)

    #stats table

    text = "<para size=15 align=left><u><b>Aircraft Summary</b></u></para>"
    aircraft_stats_title = Paragraph(text, style=styles["Normal"])
    story.append(aircraft_stats_title)
    story.append(spacer)

    today = datetime.date.today()
    last_5yr = today - datetime.timedelta(days=1825)
    # stat_objects = Stat.objects.filter(last_flown__gte=last_5yr)
    stat_objects = Stat.objects.all()

    stat_data = []
    for stat in stat_objects:
        row = [str(stat.aircraft_type), str(stat.total_time), str(stat.pilot_in_command), str(stat.second_in_command), str(stat.cross_country),
                str(stat.instructor), str(stat.dual), str(stat.solo), str(stat.instrument), str(stat.night), str(stat.simulated_instrument),
                str(stat.simulator), str(stat.landings_day), str(stat.landings_night),
                str(stat.last_flown.strftime("%m/%d/%Y")), str(stat.last_30), str(stat.last_60), str(stat.last_90), str(stat.last_180),
                str(stat.last_yr), str(stat.last_2yr), str(stat.ytd) ]

        stat_data.append(row)

    stat_header = [ "Type", "Time", "PIC", "SIC", "XC", "CFI", "Dual", "Solo",
                    "IFR", "Night", "Hood", "Sim", "D Ldg", "N Ldg",
                    "Last Flown", "30", "60", "90", "6mo", "1yr", "2yr", "Ytd"]

    stat_data.insert(0, stat_header)

    stat_table = Table(stat_data, hAlign='LEFT')

    stat_table.setStyle(tablestyle)

    story.append(stat_table)

    story.append(spacer)


    story.append(PageBreak())

    # logbook starts here

    # flight_objects = Flight.objects.filter(user=user).order_by('date')
    flight_objects = Flight.objects.filter(user=user).order_by('-date')[:100]

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

    logbook_table = Table(logbook_data, repeatRows=(1), hAlign='LEFT')

    logbook_table.setStyle(tablestyle)

    styles = getSampleStyleSheet()

    text= "<para size=15 align=left><u><b>Logbook</b></u></para>"
    logbook_title = Paragraph(text, style=styles["Normal"])
    story.append(logbook_title)
    story.append(spacer)

    story.append(logbook_table)

    #build pdf
    doc.multiBuild(story, canvasmaker=FooterCanvas)
    # doc.build(story)
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
