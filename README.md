# 🎬 CinéCampus — Student Cinema Association Web Platform

A lightweight, zero-dependency fullstack web application built for student cinema associations.
Allows members to vote for the movie of the night, pre-order their popcorn and drinks, rate & review screened movies (Letterboxd-style), and send live buzzwords for a projection-screen word cloud (Wooclap-style).
Includes an organizer staff dashboard to follow orders, toggle payment/fulfillment, and track attendance.

---

## 🚀 Quick Start

1. Open your terminal in this directory:
   ```bash
   cd /home/leelou/.gemini/antigravity/scratch/student-cinema
   ```

2. Start the server:
   ```bash
   python3 server.py
   ```

3. Open your browser at:
   ```
   http://localhost:8000
   ```

---

## 🌟 Key Features

- **🗳️ Film Voting:**
  - Members enter their name or nickname and vote for their favorite candidate film.
  - Live vote progress meters and current standings (with toggle to hide for suspense).
  - One vote per member name per session (members can switch their vote).

- **🍿 Concession Stand & Popcorn Bar:**
  - Sweet, salty butter, and caramel popcorn in multiple sizes (Medium, Large, Jumbo).
  - Cold drinks, sweets, and combo deals.
  - Interactive cart drawer with quantity adjustments.
  - "Reserve online & pay on pickup" model (cash, Lydia, Revolut, or campus card).

- **🎟️ Digital Order Pass:**
  - Generates an order code (e.g. `POP-482`) with items breakdown and live fulfillment status.
  - Instant lookup of orders by student name.

- **⭐ Letterboxd-style Film Reviews & Ratings:**
  - Members can rate screened movies (1 to 5 stars) with interactive star picker.
  - Community score card with average rating and 5-star distribution histogram.
  - Diary review feed displaying members' thoughts and ratings.
  - Members can edit/update their review anytime.

- **☁️ Wooclap-style Live Audience Word Cloud:**
  - Audience reaction arena: *"What word or feeling describes tonight's film?"*
  - Real-time word cloud where frequent words dynamically scale in size and glow in neon cinema colors.
  - Auto-polling every 4 seconds—ideal for displaying on the auditorium projection screen during post-screening debates.

- **🛡️ Association Staff Admin Mode:**
  - Accessible via the **Staff Admin** tab in the top navigation.
  - **Default Admin PIN:** `1234` (configurable in `server.py`).
  - **Live Order Board:** Mark orders as **Paid / Unpaid** and update fulfillment status (**Pending** ➔ **Preparing** ➔ **Ready** ➔ **Collected**).
  - **Attendance Analytics:** Real-time count of total unique attendees tonight (combining movie voters and snack buyers).
  - **Revenue Tracker:** Total € revenue and collected cash/card amount.
  - **Add Movie Nominations:** Propose new films with posters and synopses.
  - **Reset Movie Night:** One-click reset to start clean for the next screening night.

---

## 📁 File Structure

```text
student-cinema/
├── server.py             # HTTP server & REST API (Python standard library)
├── database.py           # SQLite database schema, seeding, and helpers
├── test_app.py           # Automated test suite (10 test scenarios)
├── cinema.db             # Local SQLite database
├── README.md             # Project documentation
└── public/               # Frontend assets
    ├── index.html        # Single-page application markup
    ├── style.css         # Cinema dark theme stylesheet
    └── app.js            # Frontend interactivity, cart, live word cloud & admin polling
```
