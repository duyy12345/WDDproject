
CREATE DATABASE IF NOT EXISTS bce_system;
USE bce_system;

-- Venues table
CREATE TABLE IF NOT EXISTS Venues (
    venue_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    capacity INT
);

-- Events table
CREATE TABLE IF NOT EXISTS Events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    start_date DATE,
    venue_id INT,
    base_price DECIMAL(10, 2),
    FOREIGN KEY (venue_id) REFERENCES Venues(venue_id)
);

-- Users table (FIXED: was using 'username', now uses 'email'; added 'role' column)
CREATE TABLE IF NOT EXISTS Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user'
);

INSERT INTO Venues (name, capacity) VALUES 
('Bristol O2 Academy', 2000),
('Bristol Museum & Art Gallery', 500),
('Ashton Gate Stadium', 27000);
