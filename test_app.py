import threading
import time
import urllib.request
import urllib.parse
import json
import socketserver
import os
import sys

from server import CinemaRequestHandler, ADMIN_PIN
from database import init_db

TEST_PORT = 8899

def run_test_server():
    init_db()
    with socketserver.TCPServer(("127.0.0.1", TEST_PORT), CinemaRequestHandler) as httpd:
        httpd.allow_reuse_address = True
        httpd.serve_forever()

def make_request(path, method="GET", data=None, headers=None):
    url = f"http://127.0.0.1:{TEST_PORT}{path}"
    req_headers = headers or {}
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            raw = response.read()
            try:
                body = raw.decode("utf-8")
                try:
                    return status, json.loads(body)
                except json.JSONDecodeError:
                    return status, body
            except UnicodeDecodeError:
                return status, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = raw.decode("utf-8")
            try:
                return e.code, json.loads(body)
            except json.JSONDecodeError:
                return e.code, body
        except UnicodeDecodeError:
            return e.code, raw

def main():
    print("🚀 Starting test server in background thread...")
    t = threading.Thread(target=run_test_server, daemon=True)
    t.start()
    time.sleep(1)

    print("\n--- TEST 1: Serve Static Index & Visuals ---")
    status, body = make_request("/")
    assert status == 200, f"Expected 200, got {status}"
    assert "KinepoliCS" in body or "KINEPOLICS" in body or "CINÉ" in body, "Index HTML not served correctly"
    print("✓ Static index HTML successfully served!")

    # Verify visuals
    v_status, _ = make_request("/visuals/kinepolics_affiche.png")
    assert v_status == 200, f"Expected 200 for poster, got {v_status}"
    logo_status, _ = make_request("/visuals/logo_kinepolics.png")
    assert logo_status == 200, f"Expected 200 for logo, got {logo_status}"
    print("✓ Visual assets successfully served!")

    print("\n--- TEST 2: GET /api/movies ---")
    status, data = make_request("/api/movies")
    assert status == 200, f"Expected 200, got {status}"
    movies = data["movies"]
    assert len(movies) >= 4, f"Expected at least 4 seeded movies, got {len(movies)}"
    print(f"✓ Retrieved {len(movies)} movie candidates.")

    movie_id_1 = movies[0]["id"]
    movie_id_2 = movies[1]["id"]

    print("\n--- TEST 3: POST /api/vote ---")
    # Alice votes for movie 1
    status, res = make_request("/api/vote", method="POST", data={"voter_name": "Alice", "movie_id": movie_id_1})
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert res["success"] is True

    # Bob votes for movie 2
    status, res = make_request("/api/vote", method="POST", data={"voter_name": "Bob", "movie_id": movie_id_2})
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert res["success"] is True

    # Alice changes her vote to movie 2
    status, res = make_request("/api/vote", method="POST", data={"voter_name": "Alice", "movie_id": movie_id_2})
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert res["updated"] is True
    print("✓ Voting and vote update tested successfully!")

    print("\n--- TEST 4: GET /api/products ---")
    status, data = make_request("/api/products")
    assert status == 200
    products = data["products"]
    assert len(products) > 0
    popcorn_item = next(p for p in products if p["category"] == "popcorn")
    drink_item = next(p for p in products if p["category"] == "drink")
    print(f"✓ Retrieved {len(products)} concession products.")

    print("\n--- TEST 5: POST /api/orders ---")
    order_payload = {
        "customer_name": "Alice",
        "items": [
            {"product_id": popcorn_item["id"], "quantity": 2},
            {"product_id": drink_item["id"], "quantity": 1}
        ],
        "notes": "Extra napkins please"
    }
    status, res = make_request("/api/orders", method="POST", data=order_payload)
    assert status == 201, f"Expected 201, got {status}: {res}"
    order = res["order"]
    order_code = order["order_code"]
    order_id = order["id"]
    expected_total = round(popcorn_item["price"] * 2 + drink_item["price"] * 1, 2)
    assert order["total_price"] == expected_total, f"Expected {expected_total}, got {order['total_price']}"
    print(f"✓ Order created: Code={order_code}, Total=€{order['total_price']}")

    print("\n--- TEST 6: PATCH /api/orders/<id> (Staff Admin Actions) ---")
    # Mark paid and set status to ready
    status, res = make_request(f"/api/orders/{order_id}", method="PATCH", data={"is_paid": 1, "status": "ready"})
    assert status == 200, f"Expected 200, got {status}: {res}"
    assert res["order"]["is_paid"] == 1
    assert res["order"]["status"] == "ready"
    print("✓ Order payment and fulfillment status updated successfully!")

    print("\n--- TEST 7: GET /api/admin/stats ---")
    status, stats = make_request("/api/admin/stats")
    assert status == 200
    # Attendees should include Alice and Bob
    assert stats["total_attendees"] >= 2, f"Expected >= 2 attendees, got {stats['total_attendees']}"
    assert stats["total_orders"] >= 1
    assert stats["paid_revenue"] >= expected_total
    print(f"✓ Admin Stats: Attendees={stats['total_attendees']}, Votes={stats['total_votes']}, Revenue=€{stats['paid_revenue']}")

    print("\n--- TEST 8: Admin Protected Route Check ---")
    # Unauthorized attempt to add movie
    status, res = make_request("/api/admin/movies", method="POST", data={"title": "Hack Movie"})
    assert status == 401, f"Expected 401 Unauthorized without PIN, got {status}"

    # Authorized attempt with PIN
    status, res = make_request(
        "/api/admin/movies", 
        method="POST", 
        data={
            "title": "Dune: Part Two",
            "year": 2024,
            "genre": "Sci-Fi / Adventure",
            "runtime": "2h 46m",
            "synopsis": "Paul Atreides unites with Chani and the Fremen while seeking revenge."
        },
        headers={"X-Admin-Pin": ADMIN_PIN}
    )
    assert status == 201, f"Expected 201, got {status}: {res}"
    print("✓ Admin PIN authentication verified!")

    print("\n--- TEST 9: Letterboxd Reviews & Ratings API ---")
    # Fetch reviews for movie 1
    status, data = make_request(f"/api/reviews?movie_id={movie_id_1}")
    assert status == 200, f"Expected 200, got {status}"
    initial_count = data["total_reviews"]

    # Post a review
    status, res = make_request("/api/reviews", method="POST", data={
        "movie_id": movie_id_1,
        "reviewer_name": "CinemaLover42",
        "rating": 5.0,
        "review_text": "Unbelievable atmosphere in the association room!"
    })
    assert status == 201, f"Expected 201, got {status}: {res}"
    assert res["updated"] is False

    # Update the review
    status, res = make_request("/api/reviews", method="POST", data={
        "movie_id": movie_id_1,
        "reviewer_name": "CinemaLover42",
        "rating": 4.5,
        "review_text": "Updated thoughts: still amazing after second thought."
    })
    assert status == 201, f"Expected 201, got {status}: {res}"
    assert res["updated"] is True

    # Check reviews count and average
    status, data = make_request(f"/api/reviews?movie_id={movie_id_1}")
    assert status == 200
    assert data["total_reviews"] == initial_count + 1
    assert data["avg_rating"] > 0
    print(f"✓ Reviews API: Total={data['total_reviews']}, Avg={data['avg_rating']}★")

    print("\n--- TEST 10: Wooclap Word Cloud API ---")
    # Post word reactions
    status, res = make_request("/api/wordcloud", method="POST", data={
        "movie_id": movie_id_1,
        "contributor_name": "Student1",
        "word": "Breathtaking"
    })
    assert status == 201, f"Expected 201, got {status}: {res}"

    status, res = make_request("/api/wordcloud", method="POST", data={
        "movie_id": movie_id_1,
        "contributor_name": "Student2",
        "word": "breathtaking!" # same word with punctuation & case
    })
    assert status == 201, f"Expected 201, got {status}: {res}"

    # Get wordcloud
    status, data = make_request(f"/api/wordcloud?movie_id={movie_id_1}")
    assert status == 200
    words = data["words"]
    breathtaking_entry = next((w for w in words if w["word"].lower() == "breathtaking"), None)
    assert breathtaking_entry is not None, "Breathtaking word not found in cloud"
    assert breathtaking_entry["count"] >= 2, f"Expected count >= 2, got {breathtaking_entry['count']}"
    print(f"✓ Word Cloud API: Aggregated '{breathtaking_entry['word']}' with count {breathtaking_entry['count']}")

    print("\n==========================================")
    print("🎉 ALL 10 TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

if __name__ == "__main__":
    main()

