from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Doctor, Patient, OTP
from django.utils import timezone
import random


class DoctorSerializer(serializers.ModelSerializer):
    """Serializer for Doctor model"""
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Doctor
        fields = ['id', 'username', 'full_name', 'phone_number', 'specialization', 
                  'hospital_name', 'registration_number', 'created_at']
        read_only_fields = ['id', 'created_at']


class PatientSerializer(serializers.ModelSerializer):
    """Serializer for Patient model"""
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    
    class Meta:
        model = Patient
        fields = ['id', 'full_name', 'phone_number', 'age', 'gender', 'disease_type',
                  'doctor', 'doctor_name', 'is_verified', 'created_at']
        read_only_fields = ['id', 'created_at', 'is_verified']


class DoctorLoginSerializer(serializers.Serializer):
    """Serializer for doctor login with username and password"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            # Authenticate user
            user = authenticate(username=username, password=password)
            
            if user:
                # Check if user has a doctor profile
                try:
                    doctor = Doctor.objects.get(user=user)
                    if not doctor.is_active:
                        raise serializers.ValidationError("This doctor account is inactive.")
                    data['user'] = user
                    data['doctor'] = doctor
                except Doctor.DoesNotExist:
                    raise serializers.ValidationError("No doctor profile found for this user.")
            else:
                raise serializers.ValidationError("Invalid username or password.")
        else:
            raise serializers.ValidationError("Must provide username and password.")
        
        return data


class PatientOTPSendSerializer(serializers.Serializer):
    """Serializer to send OTP to patient's phone number"""
    phone_number = serializers.CharField(max_length=15)
    
    def validate_phone_number(self, value):
        # Check if patient exists with this phone number
        if not Patient.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("No patient found with this phone number.")
        return value
    
    def create_otp(self):
        from notifications.sms_service import sms_service

        phone_number = self.validated_data['phone_number']

        # Delete old OTPs for this phone number
        OTP.objects.filter(phone_number=phone_number).delete()

        # Create new OTP
        otp = OTP.objects.create(phone_number=phone_number)

        # Send OTP via SMS (Twilio)
        sent = sms_service.send_otp_sms(phone_number, otp.otp_code)
        if not sent:
            print(f'⚠️  OTP SMS failed for {phone_number} — OTP: {otp.otp_code}')

        return otp


class PatientOTPVerifySerializer(serializers.Serializer):
    """Serializer to verify OTP and login patient"""
    phone_number = serializers.CharField(max_length=15)
    otp_code = serializers.CharField(max_length=6)
    
    def validate(self, data):
        phone_number = data.get('phone_number')
        otp_code = data.get('otp_code')
        
        # Check if patient exists
        try:
            patient = Patient.objects.get(phone_number=phone_number)
        except Patient.DoesNotExist:
            raise serializers.ValidationError("No patient found with this phone number.")
        
        # Check if OTP exists and is valid
        try:
            otp = OTP.objects.filter(
                phone_number=phone_number,
                otp_code=otp_code,
                is_verified=False
            ).latest('created_at')
            
            if not otp.is_valid():
                raise serializers.ValidationError("OTP has expired. Please request a new one.")
            
            # Mark OTP as verified
            otp.is_verified = True
            otp.save()
            
            # Update patient's last login
            patient.is_verified = True
            patient.last_login = timezone.now()
            patient.save()
            
            data['patient'] = patient
            
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP code.")
        
        return data


class DoctorRegistrationSerializer(serializers.Serializer):
    """Serializer for doctor registration"""
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    full_name = serializers.CharField(max_length=200)
    phone_number = serializers.CharField(max_length=15)
    specialization = serializers.CharField(max_length=100)
    hospital_name = serializers.CharField(max_length=200)
    registration_number = serializers.CharField(max_length=50)
    
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value
    
    def validate_phone_number(self, value):
        if Doctor.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already registered.")
        return value
    
    def validate_registration_number(self, value):
        if Doctor.objects.filter(registration_number=value).exists():
            raise serializers.ValidationError("Registration number already exists.")
        return value
    
    def create(self, validated_data):
        # Create user
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        
        # Create doctor profile
        doctor = Doctor.objects.create(
            user=user,
            full_name=validated_data['full_name'],
            phone_number=validated_data['phone_number'],
            specialization=validated_data['specialization'],
            hospital_name=validated_data['hospital_name'],
            registration_number=validated_data['registration_number']
        )
        
        return doctor


class PatientRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for patient registration by doctor"""
    
    class Meta:
        model = Patient
        fields = ['full_name', 'phone_number', 'age', 'gender', 'disease_type', 'doctor']
    
    def validate_phone_number(self, value):
        if Patient.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("Phone number already registered.")
        return value