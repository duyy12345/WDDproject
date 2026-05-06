// ── Admin page guard ──
const token = localStorage.getItem('token');
const role = localStorage.getItem('role');

if (!token || role !== 'admin') {
    alert('Access denied. Admins only.');
    window.location.href = 'webUI.html';
}

// ── Fetch Users ──
fetch('http://127.0.0.1:5000/api/admin/users', {
    headers: {
        'Authorization': 'Bearer ' + localStorage.getItem('token')
    }
})
.then(response => {
    if (response.status === 401 || response.status === 403) {
        // Token expired or not admin — redirect to login
        alert('Session expired. Please log in again.');
        window.location.href = 'webUI.html';
        throw new Error('Unauthorized');
    }
    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    return response.json();
})
.then(users => {
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = '';

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="status-msg">No users registered yet.</td></tr>';
        return;
    }

    users.forEach(user => {
        const roleClass = user.role.toLowerCase() === 'admin' ? 'role-admin' : 'role-user';
        const row = `<tr>
            <td><b>#${user.user_id}</b></td>
            <td>${user.email}</td>
            <td><span class="role-badge ${roleClass}">${user.role}</span></td>
        </tr>`;
        tbody.innerHTML += row;
    });
})
.catch(error => {
    if (error.message === 'Unauthorized') return; // Already handled above
    console.error('Error fetching users:', error);
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = `<tr><td colspan="3" class="error-message">
        Could not load users. Please make sure your Flask server (app.py) is running!
    </td></tr>`;
});