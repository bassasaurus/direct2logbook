from flights.models import Flight, Total, Stat, Regs, Power, Weight, Endorsement
from django.contrib.auth.decorators import login_required
import datetime
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, legal, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, SimpleDocTemplate, Spacer, TableStyle, PageBreak, LongTable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch, mm

from django.core.mail import EmailMessage
from django.core.mail import send_mail

from django.http import HttpResponse
from django.template.response import TemplateResponse

from django.views.generic import CreateView, UpdateView
from .models import Signature
from .forms import SignatureForm

def entry(object, flight):
    if not object:
        entry = '-'
    elif object == True:
        entry = str(flight.duration)
    else:
        entry = str(object)
    return entry

def title_page(canvas, doc):
    canvas.saveState()

    canvas.drawImage('pdf_output/wings.png', 103, 205, width=800, height=229)

    canvas.setFont('Helvetica-Oblique', 7)
    canvas.drawString(800, 30, "Powered by Direct2Logbook.com and ReportLab")

    canvas.setFont('Helvetica', 10)
    page_number_text = "%d" % (doc.page)
    canvas.drawCentredString(
     14 * inch/2,
     30,
     page_number_text
    )
    canvas.restoreState()

def add_later_page_number(canvas, doc):
    canvas.saveState()

    canvas.setFont('Helvetica-Oblique', 7)
    canvas.drawString(800, 30, "Powered by Direct2Logbook.com and ReportLab")

    canvas.setFont('Helvetica', 10)
    canvas.drawString(30, 50, "I certify that the entries in this logbook are true.")

    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setLineWidth(0.5)
    canvas.line(240, 50, 480, 50)

    canvas.setFont('Helvetica', 10)
    page_number_text = "%d" % (doc.page)
    canvas.drawCentredString(
        14 * inch/2,
        30,
        page_number_text
    )
    canvas.restoreState()


@login_required
def PDFView(request, user_id):

    user = request.user
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer,
                            pagesize=landscape(legal),
                            verbosity=1,
                            leftMargin=0.25*inch,
                            rightMargin=0.25*inch,
                            topMargin=0.5*inch,
                            bottomMargin=1.25*inch)
    styles = getSampleStyleSheet()

    story = []

    #cover page starts here
    spacer15= Spacer(1, 1.5*inch)
    spacer10= Spacer(1, 1.0*inch)
    spacer025= Spacer(1, .25*inch)
    spacer050= Spacer(1, .50*inch)

    story.append(spacer15)
    story.append(spacer025)
    text = "<para size=50 align=center>Logbook for {} {}</para>".format(user.first_name, user.last_name)
    title =  Paragraph(text, style=styles["Normal"])
    story.append(title)
    story.append(spacer15)
    story.append(spacer15)

    text = "<para size=15 align=center>Data current as of {}</para>".format(datetime.date.today().strftime("%m/%d/%Y"))
    title =  Paragraph(text, style=styles["Normal"])
    story.append(title)
    story.append(PageBreak())

    #summary page starts here
    spacer = Spacer(1, 0.25*inch)
    text = "<para size=15 align=left><u><b>Category and Class Summary</b></u></para>"
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
        total = Total.objects.filter(user=user).get(total=total)
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
    cat_class_tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                        ])
    total_table.setStyle(cat_class_tablestyle)

    story.append(total_table)

    story.append(spacer)

    #misc tables start here

    # role_table
    role_objects = Power.objects.filter(user=user)
    role_data = []
    for role in role_objects:
        row = [str(role.role), str(role.turbine), str(role.piston)]
        role_data.append(row)

    role_header = ["Role", "Turbine", "Piston"]
    role_data.insert(0, role_header)
    role_table = Table(role_data, hAlign="LEFT")
    role_tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                        ])
    role_table.setStyle(role_tablestyle)


    #regs_table
    regs_objects = Regs.objects.filter(user=user)
    regs_data = []
    for regs in regs_objects:
        row = [str(regs.reg_type), str(regs.pilot_in_command), str(regs.second_in_command)]
        regs_data.append(row)

    regs_header = ["FAR", "PIC", "SIC"]
    regs_data.insert(0, regs_header)
    regs_table = Table(regs_data, hAlign='LEFT')
    reg_tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                        ])

    regs_table.setStyle(reg_tablestyle)

    #weight_table
    weight_objects = Weight.objects.filter(user=user)

    weights_that_exist =[]
    for weight in weight_objects:
        if weight.total > 0.0:
            weights_that_exist.append(weight)

    weight_data = []

    for weight in weights_that_exist:
        row = [str(weight.weight), str(weight.total)]
        weight_data.append(row)

    weight_header = ['Weight', 'Total']
    weight_data.insert(0, weight_header)
    weight_table = Table(weight_data, hAlign='LEFT')
    weight_tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                        ])

    weight_table.setStyle(weight_tablestyle)

    #endoresment_table

    endorsement_objects = Endorsement.objects.filter(user=user)

    endorsements_that_exist =[]
    for endorsement in endorsement_objects:
        if endorsement.total > 0.0:
            endorsements_that_exist.append(endorsement)

    endorsement_data = []

    for endorsement in endorsements_that_exist:
        row = [str(endorsement.endorsement), str(endorsement.total)]
        endorsement_data.append(row)

    endorsement_header = ['Endorsement', 'Total']
    endorsement_data.insert(0, endorsement_header)
    endorsement_table = Table(endorsement_data, hAlign='LEFT')
    endorsement_tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                        ])

    endorsement_table.setStyle(endorsement_tablestyle)

    #misc_table
    text = "<para size=15 align=left><u><b>Misc Summary</b></u></para>"
    misc_title = Paragraph(text, style=styles["Normal"])
    story.append(misc_title)
    story.append(spacer)

    misc_data = [
                [role_table, regs_table, weight_table, endorsement_table]
                ]

    misc_table = Table(misc_data, hAlign="LEFT")
    story.append(misc_table)
    story.append(spacer)

    #aircraft stats table

    text = "<para size=15 align=left><u><b>Aircraft Summary</b></u></para>"
    aircraft_stats_title = Paragraph(text, style=styles["Normal"])
    story.append(aircraft_stats_title)
    story.append(spacer)

    today = datetime.date.today()
    last_5yr = today - datetime.timedelta(days=1825)
    # stat_objects = Stat.objects.filter(last_flown__gte=last_5yr)
    stat_objects = Stat.objects.filter(user=user).all()

    stat_data = []
    for stat in stat_objects:
        #avoids None failure when user hasn't logged time in aircraft
        date_condition = [stat.last_flown, stat.last_30, stat.last_60, stat.last_90, stat.last_180, stat.last_yr, stat.last_2yr, stat.ytd]
        if None not in date_condition:

            row = [str(stat.aircraft_type), str(stat.total_time), str(stat.pilot_in_command), str(stat.second_in_command), str(stat.cross_country),
                    str(stat.instructor), str(stat.dual), str(stat.solo), str(stat.instrument), str(stat.night), str(stat.simulated_instrument),
                    str(stat.simulator), str(stat.landings_day), str(stat.landings_night),
                    str(stat.last_flown.strftime("%m/%d/%Y")), str(stat.last_30), str(stat.last_60), str(stat.last_90), str(stat.last_180),
                    str(stat.last_yr), str(stat.last_2yr), str(stat.ytd) ]
            stat_data.append(row)

        else:
            pass



    stat_header = [ "Type", "Time", "PIC", "SIC", "XC", "CFI", "Dual", "Solo",
                    "IFR", "Night", "Hood", "Sim", "D Ldg", "N Ldg",
                    "Last Flown", "30", "60", "90", "6mo", "1yr", "2yr", "Ytd"]

    stat_data.insert(0, stat_header)



    stat_table = Table(stat_data, repeatRows=(1), hAlign='LEFT')
    stat_tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                        ])
    stat_table.setStyle(stat_tablestyle)

    story.append(stat_table)

    story.append(spacer)


    # story.append(PageBreak())

    # logbook starts here

    flight_objects = Flight.objects.filter(user=user).order_by('-date')
    # flight_objects = Flight.objects.filter(user=user).order_by('-date')[:200]

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
            appr = appr + str(approach.approach_type) + '-' + str(approach.number) + ' '

        hold = ''
        for holding in flight.holding_set.all():
            if holding.hold == True:
                hold = 'Yes'
            else:
                hold = '-'

        row = [Date, str(flight.aircraft_type), str(flight.registration), str(flight.route), str(flight.duration), PIC, SIC, XC, Night, IFR, appr, hold, Day_LDG, Night_LDG, Hood, CFI, Dual, Solo, Sim]

        logbook_data.append(row)

    logbook_data.insert(0, logbook_header)

    logbook_table = LongTable(logbook_data, repeatRows=(1), hAlign='LEFT')

    logbook_tablestyle = TableStyle([
                        ('FONT', (0,0), (-1,0), 'Helvetica-Bold', 10),
                        ('LINEBELOW',(0,0),(-1,0),1.0,colors.black),
                        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
                        ('LINEBELOW',(0,0),(-1,-1),.25,colors.black),
                        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
                        ])
    logbook_table.setStyle(logbook_tablestyle)

    styles = getSampleStyleSheet()

    text= "<para size=15 align=left><u><b>Logbook</b></u></para>"
    logbook_title = Paragraph(text, style=styles["Normal"])
    story.append(logbook_title)
    story.append(spacer)

    story.append(logbook_table)

    #build pdf
    # doc.multiBuild(story, onFirstPage=myFirstPage, onLaterPages=myLaterPages)
    doc.multiBuild(story, onFirstPage=title_page, onLaterPages=add_later_page_number)
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


class SignatureCreate(CreateView):
    model = Signature
    form_class = SignatureForm


class SignatureUpdate(UpdateView):
    model = Signature
    form_class = SignatureForm
    template = '/pdf_output/signature_update.html'
