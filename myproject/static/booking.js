const API_URL = 'http://localhost:5000/api';
const STUDENT_DISCOUNT = 0.10;
let eventData = null;

// Check authentication
function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        alert('Please login to book tickets!');
        window.location.href = 'webUI.html';
    }
}

// Get event ID from URL
function getEventId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('event');
}

// Load event details
async function loadEventDetails() {
    const eventId = getEventId();
    if (!eventId) {
        console.error('No event specified in URL.');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/events/${eventId}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to load event details');
        }

        eventData = await response.json();
        const eventDate = eventData.start_date.split('T')[0];

        document.getElementById('eventTitle').textContent = eventData.title;
        document.getElementById('eventDate').textContent = new Date(eventData.start_date).toLocaleDateString('en-GB');
        document.getElementById('eventVenue').textContent = eventData.venue_name || 'TBA';
        document.getElementById('datePicker').min = eventDate;
        document.getElementById('datePicker').value = eventDate;
        document.getElementById('basePrice').textContent = `£${eventData.base_price.toFixed(2)}`;
        updatePrice();
    } catch (error) {
        console.error('Error loading event:', error);
        document.getElementById('bookingForm').style.display = 'none';
        document.getElementById('successMessage').classList.add('show');
        document.querySelector('.success-message h3').textContent = 'Unable to load event';
        document.querySelector('.success-message p').textContent = error.message;
    }
}

// Dynamic price calculation
function updatePrice() {
    if (!eventData) return;

    const numTickets = parseInt(document.getElementById('numTickets').value) || 1;
    const isStudent = document.getElementById('studentDiscount').checked;
    const basePrice = eventData.current_price || eventData.base_price || 0;
    const discountValue = isStudent ? basePrice * STUDENT_DISCOUNT * numTickets : 0;
    const total = basePrice * numTickets - discountValue;

    document.getElementById('basePrice').textContent = `£${basePrice.toFixed(2)}`;
    document.getElementById('discount').textContent = isStudent ? `-£${discountValue.toFixed(2)}` : '£0.00';
    document.getElementById('totalPrice').textContent = `£${total.toFixed(2)}`;
    document.getElementById('finalTotal').textContent = total.toFixed(2);
}

async function submitBooking(e) {
    e.preventDefault();
    if (!eventData) return;

    const token = localStorage.getItem('token');
    const numTickets = parseInt(document.getElementById('numTickets').value) || 1;
    const eventDate = document.getElementById('datePicker').value;
    const isStudent = document.getElementById('studentDiscount').checked;

    if (!eventDate) {
        alert('Please select an event date.');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/bookings/book`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                event_id: eventData.event_id,
                num_tickets: numTickets,
                event_date: eventDate,
                is_student: isStudent
            })
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Booking failed');
        }

        document.getElementById('bookingForm').style.display = 'none';
        const success = document.getElementById('successMessage');
        success.querySelector('h3').textContent = 'Booking Confirmed!';
        success.querySelector('p').textContent = 'Your booking is complete. Booking ID: ' + result.booking_id;
        success.classList.add('show');
    } catch (error) {
        alert(error.message || 'Booking failed.');
        console.error('Booking error:', error);
    }
}

// Event Listeners
document.getElementById('numTickets').addEventListener('input', updatePrice);
document.getElementById('studentDiscount').addEventListener('change', updatePrice);
document.getElementById('datePicker').addEventListener('change', updatePrice);
document.getElementById('bookingForm').addEventListener('submit', submitBooking);

window.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadEventDetails();
});