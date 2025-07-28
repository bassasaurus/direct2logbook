import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from flights.models import Flights  # Change "yourapp" to your actual app name

print("CRUD test")


@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='testpass')


@pytest.fixture
def client_logged_in(client, user):
    client.login(username='testuser', password='testpass')
    return client


@pytest.fixture
def flight(db):
    return Flights.objects.create(
        date='2025-01-01',
        aircraft='Cessna 172',
        tail_number='N123AB',
        duration=2.5
    )

# CREATE


def test_create_flight(client_logged_in):
    url = reverse('flights_create')  # Update to your actual URL name
    data = {
        'date': '2025-07-28',
        'aircraft': 'Piper Archer',
        'tail_number': 'N456CD',
        'duration': 1.8
    }
    response = client_logged_in.post(url, data)
    assert response.status_code == 302  # Should redirect on success
    assert Flights.objects.filter(tail_number='N456CD').exists()

# READ (Detail View)


def test_read_flight_detail(client_logged_in, flight):
    url = reverse('flights_detail', args=[flight.id])
    response = client_logged_in.get(url)
    assert response.status_code == 200
    assert flight.aircraft in response.content.decode()

# UPDATE


def test_update_flight(client_logged_in, flight):
    url = reverse('flights_update', args=[flight.id])
    data = {
        'date': flight.date,
        'aircraft': 'Updated Aircraft',
        'tail_number': flight.tail_number,
        'duration': flight.duration
    }
    response = client_logged_in.post(url, data)
    assert response.status_code == 302
    flight.refresh_from_db()
    assert flight.aircraft == 'Updated Aircraft'

# DELETE


def test_delete_flight(client_logged_in, flight):
    url = reverse('flights_delete', args=[flight.id])
    response = client_logged_in.post(url)
    assert response.status_code == 302
    assert not Flights.objects.filter(id=flight.id).exists()
