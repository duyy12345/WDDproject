-- ============================================
-- BCE SYSTEM - Complete Database Schema
-- Bristol Cultural Events Management System
-- ============================================

CREATE DATABASE IF NOT EXISTS bce_system;
USE bce_system;

-- ============================================
-- 1. VENUES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS Venues (
    venue_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    capacity INT NOT NULL,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 2. USERS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS Users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    is_student BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 3. EVENTS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS Events (
    event_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    category ENUM('Exhibitions', 'Workshops', 'Musical', 'Sports') NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE DEFAULT NULL,
    duration_days INT DEFAULT 1,
    venue_id INT,
    base_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    description TEXT,
    image_url VARCHAR(500),
    status ENUM('active', 'cancelled', 'completed') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (venue_id) REFERENCES Venues(venue_id)
);

-- ============================================
-- 4. BOOKINGS TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS Bookings (
    booking_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    event_id INT NOT NULL,
    booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_date DATE NOT NULL,
    num_tickets INT NOT NULL DEFAULT 1,
    original_price DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0.00,
    student_discount DECIMAL(10,2) DEFAULT 0.00,
    final_price DECIMAL(10,2) NOT NULL,
    status ENUM('confirmed', 'cancelled', 'waiting_list') DEFAULT 'confirmed',
    cancellation_charge DECIMAL(10,2) DEFAULT 0.00,
    cancelled_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (event_id) REFERENCES Events(event_id)
);

-- ============================================
-- 5. WAITING LIST TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS WaitingList (
    wait_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    event_id INT NOT NULL,
    event_date DATE NOT NULL,
    num_tickets INT NOT NULL DEFAULT 1,
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'confirmed', 'expired') DEFAULT 'pending',
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (event_id) REFERENCES Events(event_id)
);

-- ============================================
-- 6. PRICING VIEW (Replaces broken generated column)
-- Dynamic pricing: 25% off if <10 days away AND <50% capacity sold
-- ============================================
CREATE OR REPLACE VIEW EventPricing AS
SELECT 
    e.event_id,
    e.title,
    e.base_price,
    e.start_date,
    v.capacity,
    COALESCE(SUM(b.num_tickets), 0) AS tickets_sold,
    CASE 
        WHEN DATEDIFF(e.start_date, CURDATE()) <= 10 
             AND COALESCE(SUM(b.num_tickets), 0) < (v.capacity * 0.5)
        THEN ROUND(e.base_price * 0.75, 2)
        ELSE e.base_price
    END AS current_price,
    CASE 
        WHEN DATEDIFF(e.start_date, CURDATE()) <= 10 
             AND COALESCE(SUM(b.num_tickets), 0) < (v.capacity * 0.5)
        THEN '25% Early Bird Discount'
        ELSE 'Standard Price'
    END AS pricing_note
FROM Events e
LEFT JOIN Venues v ON e.venue_id = v.venue_id
LEFT JOIN Bookings b ON e.event_id = b.event_id AND b.status = 'confirmed'
GROUP BY e.event_id, e.title, e.base_price, e.start_date, v.capacity;

-- ============================================
-- 7. INITIAL DATA - VENUES (Table 1 from spec)
-- ============================================
INSERT INTO Venues (venue_id, name, capacity, address) VALUES
(1, 'Bristol O2 Academy', 2000, 'Frogmore Street, Bristol BS2 9EY'),
(2, 'Bristol Museum & Art Gallery', 500, 'Queens Road, Bristol BS8 1RL'),
(3, 'Ashton Gate Stadium', 27000, 'Winterstoke Road, Bristol BS3 2EJ')
ON DUPLICATE KEY UPDATE name = VALUES(name);

-- ============================================
-- 8. INITIAL DATA - SAMPLE EVENTS
-- ============================================
INSERT INTO Events (title, category, start_date, end_date, duration_days, venue_id, base_price, description) VALUES
('Bristol Jazz Festival', 'Musical', '2024-07-15', '2024-07-17', 3, 1, 35.00, 'Three days of world-class jazz performances at the O2 Academy.'),
('Modern Art Exhibition', 'Exhibitions', '2024-08-01', '2024-08-14', 14, 2, 15.00, 'Contemporary art from local and international artists.'),
('Photography Workshop', 'Workshops', '2024-06-20', NULL, 1, 2, 25.00, 'Learn professional photography techniques in a hands-on workshop.'),
('Bristol City vs Bath Rugby', 'Sports', '2024-09-10', NULL, 1, 3, 45.00, 'Exciting cross-sport friendly match at Ashton Gate.'),
('Summer Music Concert', 'Musical', '2024-07-25', NULL, 1, 1, 30.00, 'Live performances from top UK indie bands.'),
('Pottery Making Workshop', 'Workshops', '2024-06-28', NULL, 1, 2, 20.00, 'Create your own pottery with expert guidance.')
ON DUPLICATE KEY UPDATE title = VALUES(title);

-- ============================================
-- 9. INITIAL DATA - ADMIN USER
-- Password: admin123 (hashed with werkzeug)
-- ============================================
INSERT INTO Users (email, password_hash, first_name, last_name, role, is_student) VALUES
('admin@bce.com', 'pbkdf2:sha256:600000$salt$hash_placeholder', 'Admin', 'User', 'admin', FALSE)
ON DUPLICATE KEY UPDATE email = VALUES(email);

-- ============================================
-- 10. USEFUL INDEXES FOR PERFORMANCE
-- ============================================
CREATE INDEX idx_events_date ON Events(start_date);
CREATE INDEX idx_events_category ON Events(category);
CREATE INDEX idx_bookings_user ON Bookings(user_id);
CREATE INDEX idx_bookings_event ON Bookings(event_id);
CREATE INDEX idx_bookings_status ON Bookings(status);
CREATE INDEX idx_waitinglist_event ON WaitingList(event_id);
CREATE INDEX idx_waitinglist_status ON WaitingList(status);

-- ============================================
-- 11. STORED PROCEDURE: Calculate Final Price
-- Handles: base price, student discount, multi-day, dynamic pricing
-- ============================================
DELIMITER //

CREATE PROCEDURE CalculateBookingPrice(
    IN p_event_id INT,
    IN p_num_tickets INT,
    IN p_is_student BOOLEAN,
    OUT p_original_price DECIMAL(10,2),
    OUT p_discount DECIMAL(10,2),
    OUT p_student_discount DECIMAL(10,2),
    OUT p_final_price DECIMAL(10,2)
)
BEGIN
    DECLARE v_current_price DECIMAL(10,2);
    
    -- Get dynamic price from view
    SELECT current_price INTO v_current_price 
    FROM EventPricing 
    WHERE event_id = p_event_id;
    
    -- Calculate
    SET p_original_price = v_current_price * p_num_tickets;
    SET p_discount = (SELECT base_price FROM Events WHERE event_id = p_event_id) * p_num_tickets - p_original_price;
    SET p_student_discount = IF(p_is_student, p_original_price * 0.10, 0.00);
    SET p_final_price = p_original_price - p_student_discount;
END //

-- ============================================
-- 12. STORED PROCEDURE: Cancel Booking
-- Handles: cancellation charges based on timing
-- ============================================
CREATE PROCEDURE CancelBooking(
    IN p_booking_id INT,
    IN p_user_id INT
)
BEGIN
    DECLARE v_event_date DATE;
    DECLARE v_final_price DECIMAL(10,2);
    DECLARE v_days_until INT;
    DECLARE v_charge DECIMAL(10,2);
    
    -- Get booking details
    SELECT event_date, final_price INTO v_event_date, v_final_price
    FROM Bookings 
    WHERE booking_id = p_booking_id AND user_id = p_user_id AND status = 'confirmed';
    
    -- Calculate days until event
    SET v_days_until = DATEDIFF(v_event_date, CURDATE());
    
    -- Cancellation charge logic
    SET v_charge = CASE
        WHEN v_days_until > 10 THEN 0.00
        WHEN v_days_until BETWEEN 3 AND 10 THEN v_final_price * 0.50
        ELSE v_final_price
    END;
    
    -- Update booking
    UPDATE Bookings 
    SET status = 'cancelled', 
        cancellation_charge = v_charge,
        cancelled_at = NOW()
    WHERE booking_id = p_booking_id AND user_id = p_user_id;
    
    -- Check waiting list
    -- (Trigger or application logic handles this)
    SELECT v_charge AS cancellation_charge, v_days_until AS days_until_event;
END //

DELIMITER ;

-- ============================================
-- VERIFICATION QUERIES
-- ============================================
SELECT 'Database created successfully' AS status;
SELECT COUNT(*) AS venue_count FROM Venues;
SELECT COUNT(*) AS event_count FROM Events;
SELECT * FROM EventPricing;