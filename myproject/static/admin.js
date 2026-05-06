// 1. Admin page guard
const token = localStorage.getItem('token');
const role  = localStorage.getItem('role');

if (!token || role !== 'admin') {
    alert('Access denied. Admins only.');
    window.location.href = 'webUI.html';
}

// 2. Form Submission Logic
document.getElementById('add-event-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const eventData = {
        title:      document.getElementById('title').value,
        category:   document.getElementById('category').value,
        start_date: document.getElementById('start_date').value,
        venue_id:   parseInt(document.getElementById('venue_id').value),
        base_price: parseFloat(document.getElementById('base_price').value)
    };

    const msgDiv = document.getElementById('message');
    msgDiv.className = "";
    msgDiv.innerText = "Processing...";
    msgDiv.style.display = "block";

    try {
        const response = await fetch('http://127.0.0.1:5000/api/admin/events/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + localStorage.getItem('token')
            },
            body: JSON.stringify(eventData)
        });

        const result = await response.json();

        if (response.ok) {
            msgDiv.innerHTML = '<i class="fas fa-check-circle"></i> Success! Event published.';
            msgDiv.className = "success";
            document.getElementById('add-event-form').reset();
        } else if (response.status === 401 || response.status === 403) {
            msgDiv.innerHTML = '<i class="fas fa-lock"></i> Session expired. Redirecting...';
            msgDiv.className = "error-msg";
            setTimeout(() => { window.location.href = 'webUI.html'; }, 2000);
        } else {
            msgDiv.innerHTML = '<i class="fas fa-times-circle"></i> Error: ' + (result.error || "Failed to add event");
            msgDiv.className = "error-msg";
        }
    } catch (error) {
        console.error("Error:", error);
        msgDiv.innerHTML = '<i class="fas fa-wifi"></i> Connection Error: Is Flask running?';
        msgDiv.className = "error-msg";
    }
});