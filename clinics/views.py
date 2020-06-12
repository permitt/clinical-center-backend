import sys
from rest_framework import viewsets, generics, filters, permissions, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import DateTimeField, Avg, IntegerField, F, Sum, OuterRef, Subquery, When, Case, FilteredRelation, \
    Q, Value as V, CharField, TimeField, ExpressionWrapper, Value
from django.db.models.functions import Coalesce
from users.models import Doctor, Schedule
from django.db.models.functions import TruncMonth, TruncDay, TruncWeek
from users.serializers import DoctorSerializer
from rest_framework import viewsets, generics, filters, permissions
from .custom_permissions import *
from .serializers import *
from django.core.mail import send_mail
from .holidayEmail import *
import datetime
from users.models import Patient
from django.db.models.functions import Concat
from django.db import IntegrityError
from django.db.models import Avg, Exists, Count

class ClinicListView(viewsets.ModelViewSet):
    serializer_class = ClinicSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['name', 'address', 'city', 'country']
    queryset = Clinic.objects.annotate(rating=Avg('ratings__rating')).all()

class HealthCardView(viewsets.ModelViewSet):
    serializer_class = HealthCardSerializer
    permission_classes = [HealthCardPermissions]

    def get_queryset(self):
        if hasattr(self.request.user, 'patient'):
            return HealthCard.objects.filter(patient=self.request.user.patient)
        if hasattr(self.request.user, 'docAccount') or hasattr(self.request.user, 'nurseAccount'):
            return HealthCard.objects.filter(patient=self.request.query_params['patient'])


class OperatingRoomView(viewsets.ModelViewSet):
    serializer_class = OperatingRoomSerializer
    permission_classes = [OperatingRoomPermissions]


    def list(self, request):
        queryset = self.get_queryset()
        if 'name' in request.query_params:
            queryset = queryset.filter(name__startswith=request.query_params['name'])
        if 'number' in request.query_params:
            queryset = queryset.filter(number=request.query_params['number'])
        if 'date' in request.query_params and 'time' in request.query_params and 'duration' in request.query_params:
            try:
                duration = int(request.query_params['duration'])
            except:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            queryset = queryset.exclude(appointment__date=request.query_params['date'], appointment__time=request.query_params['time'])

            hall_list = list(queryset)
            for hall in hall_list:
                for app in hall.appointment_set.all():
                    choosenStartTime = datetime.datetime.strptime(request.query_params['time'], '%H:%M').time()
                    choosenEndTime = time_add(choosenStartTime, duration)
                    endsBefore = choosenEndTime < app.time
                    startsAfter = choosenStartTime > time_add(app.time, app.typeOf.duration)

                    if (not (endsBefore or startsAfter)):
                        hall_list.remove(hall)
                        break
        else:
            hall_list = list(queryset)


        serializer = OperatingRoomSerializer(hall_list, many=True)
        appTypeSerializer = AppointmentTypeSerializer
        operationSerializer = OperationSerializer
        dates = {}
        for hall in queryset :
            dates[hall.name] = []
            for app in hall.appointment_set.all() :
                dates[hall.name].append({'date': app.date, 'time': app.time, 'type': appTypeSerializer(app.typeOf).data })
            for operation in hall.operation_set.all():
                dates[hall.name].append(
                    {'date': operation.date, 'time': operation.time, 'type': 'operation'})
        return Response(status=status.HTTP_200_OK, data={"halls": serializer.data , "reservedDates": dates}, content_type='application/json')

    def get_queryset(self):
        user = self.request.user
        query = OperatingRoom.objects.filter(clinic=user.adminAccount.employedAt)

        return query

    def destroy(self, request,pk) :
        instance = self.get_object()
        if (len(instance.appointment_set.all()) > 0 or len(instance.operation_set.all())):
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg': "Reserved hall can't be deleted"})
        else:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if (len(instance.appointment_set.all()) > 0 or len(instance.operation_set.all())):
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg': "Reserved hall can't be changed"})
        try:
            self.perform_update(serializer)
        except IntegrityError as ext:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED,
                            data={'msg': "Operating room with given name already exists"})

        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except IntegrityError as ext:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED,
                            data={'msg': "Operating room with given name already exists"})

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    queryset = Appointment.objects.all()
    ordering_fields = ['typeOf', 'date']

    def get_queryset(self):

        if hasattr(self.request.user, 'patient'):
            if self.request.method == "PUT":
                return Appointment.objects.all()

            if 'clinic' in self.request.query_params:
                return Appointment.objects \
                    .filter(patient__isnull=True, clinic=self.request.query_params['clinic']).annotate(
                    type_name=F("typeOf__typeName"),
                    operating_room_name=Concat(F("operatingRoom__name"), Value(' '), F("operatingRoom__number"),
                                               output_field=models.CharField()),
                    clinic_name=F("clinic__name"),
                    price=F("typeOf__prices__price"),
                )
            else:
                return Appointment.objects\
                    .filter(patient=self.request.user.patient, date__lt=datetime.datetime.now(), operatingRoom__isnull = False).annotate(
                    type_name=F("typeOf__typeName"),
                    operating_room_name=Concat(F("operatingRoom__name"), Value(' '), F("operatingRoom__number"), output_field=models.CharField()),
                    clinic_name=F("clinic__name"),
                    price=F("typeOf__prices__price"),
                    )
        if hasattr(self.request.user, 'adminAccount'):
            if 'all' in self.request.query_params :
                return Appointment.objects \
                    .filter(clinic=self.request.user.adminAccount.employedAt, ).exclude(patient__isnull=True).annotate(
                    type_name=F("typeOf__typeName"),
                    operating_room_name=F("operatingRoom__name"),
                    doctor_name=F("doctor__firstName"),
                    price=F("typeOf__prices__price"),
                    duration=F("typeOf__duration")
                )

            else:
                print(Appointment.objects.all())
                return Appointment.objects \
                    .filter(patient=None, clinic=self.request.user.adminAccount.employedAt).annotate(
                    type_name=F("typeOf__typeName"),
                    operating_room_name=Concat(F('operatingRoom__name'), V(' '), F('operatingRoom__number'),
                                               output_field=CharField()),
                    doctor_name=Concat(F('doctor__firstName'), V(' '), F('doctor__lastName'), output_field=CharField()),
                    price=F("typeOf__prices__price"),
                    duration=F("typeOf__duration")
                )


        return Appointment.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class AppointmentTypeView(viewsets.ModelViewSet):
    queryset = AppointmentType.objects.all()
    permission_classes = [AppointmentTypePermissions]
    serializer_class = AppointmentTypeSerializer

    def get_queryset(self):
        user = self.request.user
        #dodavanje za pacijenta
        if hasattr(user, 'patient'):
            return AppointmentType.objects.all()

        if hasattr(user, 'adminAccount'):
            query = AppointmentType.objects.filter(clinic=user.adminAccount.employedAt).select_related()
        elif hasattr(user, 'docAccount') :
            query = AppointmentType.objects.filter(specializations__doctor__email=user.docAccount.email)

        return query

    def destroy(self, request,pk) :
        instance = self.get_object()
        now = datetime.datetime.now().date()
        for app in instance.appointment_set.all():
            if (now < app.date):
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg': "This type has following appointments and can't be deleted"})

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        now = datetime.datetime.now().date()
        for app in instance.appointment_set.all():
            if (now < app.date):
                return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg': "This type has following appointments and can't be changed"})
        try:
            self.perform_update(serializer)
        except IntegrityError as ext:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED, data={'msg': "Type with given name already exists"})

        return Response(serializer.data)

class HolidayRequestView(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = HolidaySerializer

    def get_queryset(self):
        user = self.request.user
        userLogged = ClinicAdmin.objects.filter(email=user.username).select_related()
        queryset = Holiday.objects.select_related('employee')\
            .filter(resolved=False) \
            .annotate(clinic=Case(When(employee__docAccount__isnull=False, then=F('employee__docAccount__employedAt__pk')),
                                   When(employee__nurseAccount__isnull=False, then=F('employee__nurseAccount__employedAt__pk')),
                                   output_field=CharField()))\
            .annotate(name=Case(When(employee__docAccount__isnull=False, then=Concat('employee__docAccount__firstName',V(' '), 'employee__docAccount__lastName')),
                                   When(employee__nurseAccount__isnull=False, then=Concat('employee__nurseAccount__firstName', V(' '), 'employee__nurseAccount__lastName')),
                      output_field = CharField()))\
            .annotate(email=Case(When(employee__docAccount__isnull=False, then=F('employee__docAccount__email')),
                                   When(employee__nurseAccount__isnull=False, then=F('employee__nurseAccount__email')),
                                   output_field=CharField()))\
            .filter(clinic=userLogged.values('employedAt')[:1]).all()

        return queryset



@api_view(["POST"])
def resolveRequest(request,pk):
    user = request.user
    if (not user):
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    try:
        decision = request.data['decision']
        holidayRequest = Holiday.objects.select_related('employee').get(pk=pk)
        to_emails = [holidayRequest.employee]
        if (not decision):
            text = request.data['text']
            send_mail(HOLIDAY_REQUEST_TITLE,
                      HOLIDAY_REJECTED_REQUEST_BODY % (text),
                      settings.EMAIL_HOST_USER,
                      to_emails,
                      fail_silently=True)
        else:
            send_mail(HOLIDAY_REQUEST_TITLE,
                      HOLIDAY_APPROVED_REQUEST_BODY % (holidayRequest.startDate.strftime("%m/%d/%Y"), holidayRequest.endDate.strftime("%m/%d/%Y")),
                      settings.EMAIL_HOST_USER,
                      to_emails,
                      fail_silently=True)

    except:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg': "Invalid parameters."})

    holidayRequest.approved = decision
    holidayRequest.resolved = True
    holidayRequest.save()

    return Response(status=status.HTTP_200_OK)


def time_add(time, duration):
    start = datetime.datetime(
        2000, 1, 1,
        hour=time.hour, minute=time.minute, second=time.second)
    end = start + datetime.timedelta(minutes=duration)
    return end.time()

@api_view(["POST"])
def appointmentCheck(request):

    try:
        date = datetime.datetime.strptime(request.data['data']['appointmentDate'], '%Y-%m-%d')
        dateDay = date.weekday()
        appointmentType = request.data['data']['appointmentType']
    except:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg':"Invalid parameters."})
    try:
        schedule = Schedule.objects.filter(employee_id = OuterRef('email'), day=dateDay)
        appTypes = AppointmentType.objects.filter(clinic = OuterRef('employedAt'), typeName=appointmentType)
        doctors = Doctor.objects\
            .annotate(busyHours = Coalesce(Sum(Case(When(appointments__date=date, then='appointments__typeOf__duration'))), 0),
                      startTime= Subquery(schedule.values('startTime')[:1]),
                      endTime = Subquery(schedule.values('endTime')[:1]),
                      rating = Avg('ratings__rating'),
                      duration = Subquery(appTypes.values('duration')),
                      ) \
            .filter(specializations__typeOf__typeName=appointmentType, busyHours__lte=((F('endTime')-F('startTime'))/60000000)-F('duration')).distinct()

        priceList = PriceList.objects.filter(clinic=OuterRef('id'), appointmentType__typeName=appointmentType)
        appointments = []
        docs_on_holiday = []

        for doc in doctors:
            holiday = Holiday.objects.filter(employee=doc.user, startDate__lte=date, endDate__gte=date, approved=True,
                                             resolved=True)
            if len(holiday) > 0:
                docs_on_holiday.append(doc.email)

            doctorElement = {'doctor':doc.email, 'time':[]}
            time = doc.startTime
            endTime = doc.endTime
            appointmentsQS = Appointment.objects.filter(doctor=doc, date=date)
            duration = doc.duration

            while(time_add(time, duration) <= endTime):

                time_advanced = False
                for app in appointmentsQS:
                    appEndTime = time_add(app.time, app.typeOf.duration)
                    nextEndTime = time_add(time, duration)
                    if (app.time <= time < appEndTime or app.time < nextEndTime <= appEndTime):
                        time = appEndTime
                        time_advanced = True
                    elif(time <= app.time < nextEndTime or time < appEndTime <= nextEndTime ):
                        time = appEndTime
                        time_advanced = True

                if time_advanced:
                    continue

                doctorElement['time'].append(time)
                time = time_add(time, duration)

            appointments.append(doctorElement)
        doctors = doctors.exclude(email__in=docs_on_holiday)
        clinics = Clinic.objects. \
            annotate(rating=Avg('ratings__rating'), appointmentPrice=Subquery(priceList.values('price'))). \
            filter(doctors__in=doctors).distinct()
        print(request.data)
        if request.data['queryParams']['clinicLocation'] != '':
            clinics = clinics.filter(address=request.data['queryParams']['clinicLocation'])
        if request.data['queryParams']['clinicMinRating'] != '':
            clinics = clinics.filter(rating__gte=request.data['queryParams']['clinicMinRating'])
        if request.data['queryParams']['clinicMaxRating'] != '':
            clinics = clinics.filter(rating__lte=request.data['queryParams']['clinicMaxRating'])

        if request.data['queryParams']['doctorName'] != '':
            doctors = doctors.filter(firstName__startswith=request.data['queryParams']['doctorName'])
        if request.data['queryParams']['doctorLastName'] != '':
            doctors = doctors.filter(lastName__startswith=request.data['queryParams']['doctorLastName'])
        if request.data['queryParams']['doctorMinRating'] != '':
            doctors = doctors.filter(rating__gte=request.data['queryParams']['doctorMinRating'])
        if request.data['queryParams']['doctorMaxRating'] != '':
            doctors = doctors.filter(rating__lte=request.data['queryParams']['doctorMaxRating'])
        print(doctors, clinics)

        clinics = clinics.filter(doctors__in=doctors)
        docSer = DoctorSerializer(doctors, many=True)
        clinicSer = ClinicSerializer(clinics, many=True)

        return Response(status=status.HTTP_200_OK, data={"doctors": docSer.data, "clinics": clinicSer.data, "availableTerms":appointments}, content_type='application/json')
    except Exception as inst:
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg':'Cannot book an appointment.'})



class OperationView(viewsets.ModelViewSet):
    serializer_class = OperationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'patient'):
            return Operation.objects.filter(patient=self.request.user.patient,date__lt=datetime.datetime.now())\
                            .annotate(
                            operatingRoom_name=F("operatingRoom__name"),
                            clinic_name=F("clinic__name"),
            )

        return Operation.objects.all()

class DoctorRatingView(viewsets.ModelViewSet):
    serializer_class = DoctorRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'patient'):
            return DoctorRating.objects.filter(patient=self.request.user.patient)

        return Operation.objects.all()

class ClinicRatingView(viewsets.ModelViewSet):
    serializer_class = ClinicRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'patient'):
            return ClinicRating.objects.filter(patient=self.request.user.patient)

        return ClinicRating.objects.all()

@api_view(["POST"])
def scheduleAppointment(request):
    user = request.user
    if (not user or not hasattr(user, 'docAccount')):
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    data = request.data
    try:
        patient = Patient.objects.filter(email=data['patient']).get()
        if (not patient):
            raise Exception
        time = datetime.datetime.strptime(data['time'], '%H:%M').time()
        date = datetime.datetime.strptime(data['date'], '%Y-%m-%d')
        type = data['type']
        if (type != 'operation' and type != 'appointment'):
            raise Exception
        if (type == 'appointment'):
            typeApp = data['typeApp']
            typeObject = AppointmentType.objects.get(id=typeApp)
            if (not typeObject):
                raise Exception
        else:
            duration = int(data['duration'])
    except:

        return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg':"Invalid parameters."})
    doctor = user.docAccount
    #check if doctor is specialized for choosen type
    if (type=='appointment'):
        duration=typeObject.duration
        specialized = doctor.specializations.get(typeOf__id=typeApp)
        if not(specialized):
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'msg': 'Doctor is not specialized for choosen type.'})
    #check if doctor is on holiday
    holidays = user.holiday.filter(approved=True, startDate__lte=date, endDate__gte=date)
    if (len(holidays) > 0):
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg': 'Doctor is on holiday during choosen date.'})
    # check if doctor works that day in that time
    doctorSchedule = doctor.schedule.filter(day=date.weekday(),startTime__lte=time,endTime__gt=time_add(time, duration))
    if (len(doctorSchedule) == 0):
        return Response(status=status.HTTP_400_BAD_REQUEST,
                        data={'msg': 'Choosen time and day is not in working hours of doctor'})
    # check if doctor has another appointment or operation in choosen time
    date = date.date()
    for app in doctor.appointments.all():
        if (not (app.date == date)):
            continue
        choosenEndTime = time_add(time, duration)
        endsBefore = choosenEndTime < app.time
        startsAfter = time > time_add(app.time, app.typeOf.duration)
        if (not (endsBefore or startsAfter)):
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'msg': 'Doctor has another appointment in choosen time.'})

        # check if doctor has another operation in choosen time
        for operation in doctor.operations.all():
            if (not (operation.date == date)):
                continue
            choosenEndTime = time_add(time, duration)
            endsBefore = choosenEndTime < operation.time
            startsAfter = time > time_add(app.time, operation.duration)
            if (not (endsBefore or startsAfter)):
                return Response(status=status.HTTP_400_BAD_REQUEST,
                                data={'msg': 'Doctor has another operation in choosen time.'})

    if (type == 'appointment'):
        newAppointment = Appointment(doctor=doctor,patient=patient,time=time,date=date, clinic=doctor.employedAt, typeOf_id=typeApp)
        newAppointment.save()
    else :
        newOperation = Operation(clinic=doctor.employedAt, patient=patient, date=date, time=time, duration=duration)
        newOperation.save()
        newOperation.doctors.add(doctor)

    return Response(status=status.HTTP_200_OK, data={'msg': 'Successfully scheduled.'})


@api_view(["GET"])
def income(request):
    user = request.user
    if (not user):
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    if not('start' in request.query_params and 'end' in request.query_params) :
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'msg':"Invalid parameters."})
    start = request.query_params['start']
    end = request.query_params['end']
    income = Appointment.objects.filter(date__lte=end,date__gte=start).only('income')\
        .all()\
        .aggregate(income=Coalesce(Sum('typeOf__prices__price'),0))


    return Response(status=status.HTTP_200_OK, data=income)

@api_view(["GET"])
def reports(request):
    user = request.user
    if (not user):
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    clinic = Clinic.objects\
        .annotate(rating=Avg('ratings__rating')) \
        .prefetch_related('doctors') \
        .get(id=user.adminAccount.employedAt.id)

    statsMonthly = (Appointment.objects
             .annotate(month=TruncMonth('date'))
             .values('month')
             .annotate(num=Count('id'))
             .order_by()
             )

    statsDaily = (Appointment.objects
             .annotate(day=TruncDay('date'))
             .values('day')
             .annotate(num=Count('id'))
             .order_by()
             )

    statsWeekly = (Appointment.objects
                  .annotate(week=TruncWeek('date'))
                  .values('week')
                  .annotate(num=Count('id'))
                  .order_by()
                  )

    clinicSerializer = ClinicSerializer(clinic, many=False)
    doctorSerializer = DoctorSerializer(clinic.doctors.annotate(rating=Coalesce(Avg('ratings__rating'),0)), many=True)

    return Response(status=status.HTTP_200_OK, data={
        'clinic': clinicSerializer.data,
        "doctors": doctorSerializer.data,
        "monthly" : statsMonthly,
        "daily": statsDaily,
        "weekly": statsWeekly
    })


@api_view(["GET"])
def adminClinic(request):
    user = request.user
    if (not user):
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    if (not hasattr(user,'adminAccount')):
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    clinic = Clinic.objects\
        .annotate(rating=Avg('ratings__rating')) \
        .get(id=user.adminAccount.employedAt.id)

    clinicSerializer = ClinicSerializer(clinic, many=False)

    return Response(status=status.HTTP_200_OK, data={'clinic': clinicSerializer.data})

@api_view(["POST"])
def appTerm(request):
    user = request.user
    if (not user):
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    try:
        doctor = request.data['doctor']
        time = request.data['time']
        date = request.data['date']
        type = request.data['type']
        hall = request.data['hall']
        appointment = Appointment.objects.create(date=date, time=time, typeOf_id=int(type), operatingRoom_id=int(hall),
                                                 doctor_id=doctor, clinic=request.user.adminAccount.employedAt)
    except:
        return Response(status=status.HTTP_400_BAD_REQUEST, data= {'msg':"InvalidParameters"})



    app = Appointment.objects.annotate(
                    type_name=F("typeOf__typeName"),
        operating_room_name=Concat(F("operatingRoom__name"), Value(' '), F("operatingRoom__number"),
                                   output_field=models.CharField()),
                    doctor_name=Concat(F('doctor__firstName'), V(' '), F('doctor__lastName'), output_field=CharField()),
                    price=F("typeOf__prices__price"),
                    duration=F("typeOf__duration")
                ).get(pk=appointment.pk)

    return Response(status=status.HTTP_200_OK,data={'app': AppointmentSerializer(app,many=False).data})