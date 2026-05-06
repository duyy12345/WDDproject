const API_URL = 'http://localhost:5000/api';

function showHome() {
    document.getElementById('main-content').style.display = 'block';
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('signup-section').style.display = 'none';
    document.getElementById('nav-home').classList.add('active');
    document.getElementById('nav-login').classList.remove('active');
    fetchEvents();
}

function showLogin() {
    document.getElementById('main-content').style.display = 'none';
    document.getElementById('login-section').style.display = 'block';
    document.getElementById('signup-section').style.display = 'none';
    document.getElementById('nav-login').classList.add('active');
    document.getElementById('nav-home').classList.remove('active');
}

function toggleAuthForms(formType) {
    if (formType === 'signup') {
        document.getElementById('login-section').style.display = 'none';
        document.getElementById('signup-section').style.display = 'block';
    } else {
        document.getElementById('login-section').style.display = 'block';
        document.getElementById('signup-section').style.display = 'none';
    }
}

function checkAuth() {
    const token = localStorage.getItem('token');
    if (token) {
        document.getElementById('nav-login').style.display = 'none';
        document.getElementById('nav-logout').style.display = 'inline-block';
    } else {
        document.getElementById('nav-login').style.display = 'inline-block';
        document.getElementById('nav-logout').style.display = 'none';
    }
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    checkAuth();
    alert('Logged out successfully!');
    showHome();
}

async function fetchEvents() {
    try {
        const response = await fetch(`${API_URL}/events`);
        const events = await response.json();
        const container = document.getElementById('events-container');
        container.innerHTML = ''; 

        if (events.length === 0) {
            container.innerHTML = '<p style="text-align: center; grid-column: 1 / -1;">No events found in the database. Please add some from the Admin panel!</p>';
            return;
        }

        events.forEach(event => {
            const priceDisplay = event.base_price > 0 ? `£${event.base_price}` : 'Free Entry';
            const priceClass = event.base_price > 0 ? '' : 'free';
            
            const randomImgId = event.event_id % 10; 
            const imgUrl = `https://images.unsplash.com/photo-1514525253161-7a46d19cd819?ixlib=rb-4.0.3&auto=format&fit=crop&w=600&q=80&sig=${randomImgId}`;

            const card = `
                <div class="event-card">
                    <img src="${imgUrl}" alt="${event.title}" class="event-img">
                    <div class="event-content">
                        <span class="event-category">${event.category || 'Event'}</span>
                        <h3 class="event-title">${event.title}</h3>
                        
                        <div class="event-details">
                            <p><i class="far fa-calendar-alt"></i> ${new Date(event.start_date).toLocaleDateString('en-GB')}</p>
                            <p><i class="fas fa-map-marker-alt"></i> ${event.venue_name || 'TBA'}</p>
                        </div>
                        
                        <div class="event-footer">
                            <span class="price ${priceClass}">${priceDisplay}</span>
                            <a href="#" class="btn-book" onclick="bookEvent(${event.event_id}, event)">Book Now</a>
                        </div>
                    </div>
                </div>
            `;
            container.innerHTML += card;
        });
    } catch (error) {
        console.error("Error fetching events:", error);
        const container = document.getElementById('events-container');
        if (container) {
            container.innerHTML = '<p style="text-align: center; color: red;">Failed to load events. Is the Flask backend running?</p>';
        }
    }
}

// Login Form Listener
const loginForm = document.getElementById('login-form');
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;

        try {
            const response = await fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                localStorage.setItem('token', data.token);
                localStorage.setItem('role', data.role);
                checkAuth();
                
                document.getElementById('email').value = '';
                document.getElementById('password').value = '';
                document.getElementById('login-error').innerText = '';
                
                alert('Login successful!');
                
                if (data.role === 'admin') {
                    if(confirm('Welcome Admin! Do you want to go to the Admin Dashboard?')) {
                        window.location.href = 'admin.html'; 
                        return;
                    }
                }
                showHome();
            } else {
                document.getElementById('login-error').innerText = data.error || 'Login failed';
            }
        } catch (error) {
            console.error("Login error:", error);
            document.getElementById('login-error').innerText = 'Server error. Please try again.';
        }
    });
}

async function handleSignup() {
    const email = document.getElementById('signup-email').value; 
    const password = document.getElementById('signup-password').value;

    const response = await fetch(`${API_URL}/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }) 
    });

    const data = await response.json();
    
    if (response.ok) {
        alert("Account created successfully! Please login.");
        document.getElementById('signup-email').value = '';
        document.getElementById('signup-password').value = '';
        toggleAuthForms('login'); 
    } else {
        alert("Error: " + (data.error || 'Registration failed'));
    }
}

function bookEvent(id, e) {
    e.preventDefault();
    if (!localStorage.getItem('token')) {
        alert('Please login to book tickets!');
        showLogin();
        return;
    }
    window.location.href = `booking.html?event=${id}`;
}

// Initialize page on load
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    showHome();
});