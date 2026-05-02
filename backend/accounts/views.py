from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from .models import Doctor, Patient, OTP
from .serializers import (
    DoctorSerializer, PatientSerializer, DoctorLoginSerializer,
    PatientOTPSendSerializer, PatientOTPVerifySerializer,
    DoctorRegistrationSerializer, PatientRegistrationSerializer
)


def get_tokens_for_user(user, user_type, user_id):
    refresh = RefreshToken.for_user(user)
    refresh['user_type'] = user_type
    # Do NOT override user_id — RefreshToken.for_user already sets it correctly
    # Overriding it with doctor.id causes type mismatch (string vs int)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

    


@api_view(['POST'])
@permission_classes([AllowAny])
def doctor_login(request):
    """Doctor login with username and password"""
    serializer = DoctorLoginSerializer(data=request.data)

    if serializer.is_valid():
        user   = serializer.validated_data['user']
        doctor = serializer.validated_data['doctor']
        tokens = get_tokens_for_user(user, 'doctor', doctor.id)

        return Response({
            'success': True,
            'message': 'Login successful',
            'data': {
                'tokens':    tokens,
                'user_type': 'doctor',
                'doctor':    DoctorSerializer(doctor).data
            }
        }, status=status.HTTP_200_OK)

    return Response({
        'success': False,
        'message': 'Login failed',
        'errors':  serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def patient_send_otp(request):
    """Send OTP to patient's phone number"""
    serializer = PatientOTPSendSerializer(data=request.data)

    if serializer.is_valid():
        otp = serializer.create_otp()
        return Response({
            'success': True,
            'message': 'OTP sent to registered phone number',
            'data': {
                'phone_number': otp.phone_number,
                'expires_at':   otp.expires_at
            }
        }, status=status.HTTP_200_OK)

    return Response({
        'success': False,
        'message': 'Failed to send OTP',
        'errors':  serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def patient_verify_otp(request):
    """Verify OTP and login patient"""
    serializer = PatientOTPVerifySerializer(data=request.data)

    if serializer.is_valid():
        patient = serializer.validated_data['patient']

        # FIX: is_active must be True — False causes 401 on ALL requests
        user, created = User.objects.get_or_create(
            username=f"patient_{patient.phone_number}",
            defaults={'is_active': True}
        )

        # Fix existing inactive patient users
        if not user.is_active:
            user.is_active = True
            user.save()

        tokens = get_tokens_for_user(user, 'patient', patient.id)

        return Response({
            'success': True,
            'message': 'Login successful',
            'data': {
                'tokens':    tokens,
                'user_type': 'patient',
                'patient':   PatientSerializer(patient).data
            }
        }, status=status.HTTP_200_OK)

    return Response({
        'success': False,
        'message': 'OTP verification failed',
        'errors':  serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def doctor_register(request):
    """Register a new doctor"""
    serializer = DoctorRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        doctor = serializer.save()

        # FIX: Ensure doctor user is active immediately after registration
        user = doctor.user
        if not user.is_active:
            user.is_active = True
            user.save()

        return Response({
            'success': True,
            'message': 'Doctor registered successfully',
            'data': {
                'doctor': DoctorSerializer(doctor).data
            }
        }, status=status.HTTP_201_CREATED)

    return Response({
        'success': False,
        'message': 'Registration failed',
        'errors':  serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def patient_register(request):
    """Register a new patient (by doctor)"""
    serializer = PatientRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        patient = serializer.save()
        return Response({
            'success': True,
            'message': 'Patient registered successfully',
            'data': {
                'patient': PatientSerializer(patient).data
            }
        }, status=status.HTTP_201_CREATED)

    return Response({
        'success': False,
        'message': 'Registration failed',
        'errors':  serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """Get current logged-in user details"""
    try:
        doctor = Doctor.objects.get(user=request.user)
        return Response({
            'success': True,
            'data': {
                'user_type': 'doctor',
                'doctor':    DoctorSerializer(doctor).data
            }
        }, status=status.HTTP_200_OK)
    except Doctor.DoesNotExist:
        pass

    if request.user.username.startswith('patient_'):
        phone_number = request.user.username.replace('patient_', '')
        try:
            patient = Patient.objects.get(phone_number=phone_number)
            return Response({
                'success': True,
                'data': {
                    'user_type': 'patient',
                    'patient':   PatientSerializer(patient).data
                }
            }, status=status.HTTP_200_OK)
        except Patient.DoesNotExist:
            pass

    return Response({
        'success': False,
        'message': 'User not found'
    }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_patients(request):
    """
    Get all patients of the currently logged-in doctor.
    FIX: Uses request.user from JWT token — NOT hardcoded id=1.
    Each doctor sees ONLY their own patients.
    """
    try:
        doctor   = Doctor.objects.get(user=request.user)
        patients = Patient.objects.filter(doctor=doctor, is_active=True)

        return Response({
            'success': True,
            'data': {
                'total_patients': patients.count(),
                'patients':       PatientSerializer(patients, many=True).data
            }
        }, status=status.HTTP_200_OK)

    except Doctor.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Doctor profile not found. Please login as a doctor.'
        }, status=status.HTTP_403_FORBIDDEN)

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_patient(request, patient_id):
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response(
            {'success': False, 'message': 'Only doctors can delete patients.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)
    patient_name = patient.full_name
    patient.delete()

    return Response(
        {'success': True, 'message': f'Patient "{patient_name}" deleted successfully.'},
        status=status.HTTP_200_OK,
    )