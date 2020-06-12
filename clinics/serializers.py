from rest_framework import serializers
from .models import *
import datetime
from users.serializers import DoctorSerializer


from users.models import ClinicAdmin


class ClinicSerializer(serializers.ModelSerializer):
    rating = serializers.DecimalField(decimal_places=2, max_digits=4)
    appointmentPrice = serializers.SerializerMethodField('get_price')

    def get_price(self,obj):
        return getattr(obj, 'appointmentPrice', None)

    class Meta:
        model = Clinic
        fields = '__all__'
        depth = 1

class AppointmentSerializer(serializers.ModelSerializer):
    type_name = serializers.SerializerMethodField('get_type_name')
    operating_room_name = serializers.SerializerMethodField('get_room_name')
    clinic_name = serializers.SerializerMethodField('get_clinic_name')
    price = serializers.SerializerMethodField('get_price')
    doctor_name = serializers.StringRelatedField()
    duration = serializers.StringRelatedField()


    def get_type_name(self, obj):
        return getattr(obj, "type_name", None)


    def get_room_name(self, obj):
        return getattr(obj, "operating_room_name", None)

    def get_clinic_name(self, obj):
        return getattr(obj, "clinic_name", None)

    def get_price(self, obj):
        return getattr(obj, 'price', None)

    class Meta:
        model = Appointment
        fields = '__all__'

class PriceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceList
        fields = ['price']

class AppointmentTypeSerializer(serializers.BaseSerializer):
    def create(self, validated_data):
        userLogged = ClinicAdmin.objects.filter(email=self.context['request'].user.username).get()
        type = AppointmentType(typeName=validated_data['typeName'], duration=validated_data['duration'], clinic=userLogged.employedAt)
        type.save()
        price = validated_data['price']
        priceListItem = PriceList.objects.create(price=price, clinic=type.clinic, appointmentType=type)
        priceListItem.save()

        return type

    def to_internal_value(self, data):
        price = data.get('price')
        typeName = data.get('typeName')
        duration = data.get('duration')

        if not price:
            raise serializers.ValidationError({
                'price': 'This field is required.'
            })
        if not typeName:
            raise serializers.ValidationError({
                'typeName': 'This field is required.'
            })
        if not duration:
            raise serializers.ValidationError({
                'duration': 'This field is required.'
            })
        try:
            int(duration)
        except ValueError:
            raise serializers.ValidationError({
                'duration': 'This field must be integer.'
            })

        try:
            int(price)
        except ValueError:
            raise serializers.ValidationError({
                'price': 'This field must be integer.'
            })

        return {
            'price': int(price),
            'typeName': typeName,
            'duration': int(duration)
        }

    def to_representation(self, instance):
        query = instance.prices.all()
        price = query[0].price

        return {
            'duration': instance.duration,
            'typeName': instance.typeName,
            'price': price,
            'id': instance.id,
            'clinicId': instance.clinic_id
        }

    def update(self, instance,validated_data):
        print(validated_data)

        instance.typeName = validated_data['typeName']
        instance.duration = validated_data['duration']
        newPrice = validated_data['price']


        instance.save()
        price = instance.prices.all()[0]
        price.price = newPrice
        price.save()



        return instance


class OperatingRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatingRoom
        exclude = ['clinic']

    def create(self, validated_data):
        requestBody = self.context['request'].data

        name = validated_data.get("name", None)
        number = validated_data.get("password", None)
        userLogged = ClinicAdmin.objects.filter(email=self.context['request'].user.username).get()
        clinicId = userLogged.employedAt
        operatingRoom = OperatingRoom(**validated_data, clinic=clinicId)
        operatingRoom.save()

        return operatingRoom


class DoctorRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorRating
        fields = '__all__'

class ClinicRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicRating
        fields = '__all__'

class HolidaySerializer(serializers.ModelSerializer):
    name = serializers.StringRelatedField()
    email = serializers.StringRelatedField()
    clinic = serializers.StringRelatedField()

    class Meta:
        model = Holiday
        fields = ['id','clinic','startDate', 'endDate', 'approved','name','email']

    def validate(self, data):

        if data['startDate'] > data['endDate']:
            raise serializers.ValidationError("End date must occur after start date")
        now = datetime.datetime.now().date()
        if data['startDate'] < now:
            raise serializers.ValidationError("start date must occur after today's date")
        return data

    def create(self, validated_data):
        requestBody = self.context['request'].data
        user = self.context['request'].user
        holiday = Holiday(**validated_data, employee=user)
        holiday.save()


        return holiday

class DiagnosisReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisReport
        fields = '__all__'

class HealthCardSerializer(serializers.ModelSerializer):
    reports = DiagnosisReportSerializer(read_only=True, many=True)

    class Meta:
        model = HealthCard

        fields = '__all__'

class OperationSerializer(serializers.ModelSerializer):
    operatingRoom_name = serializers.SerializerMethodField('get_room_name')
    clinic_name = serializers.SerializerMethodField('get_clinic_name')

    def get_room_name(self, obj):
        return getattr(obj, "operatingRoom_name", None)

    def get_clinic_name(self, obj):
        return getattr(obj, "clinic_name", None)


    class Meta:
        model = Operation
        fields = '__all__'
