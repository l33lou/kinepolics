import http.server
import socketserver
import json
import os
import mimetypes
import urllib.parse
import random
import string
import hashlib
import base64
import sqlite3

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VISUALS_DIR = os.path.join(BASE_DIR, "visuals")
ADMIN_PIN = "1234"  # Default association admin PIN

# ==============================================================================
# DATABASE SCHEMA, INITIALIZATION & SEEDING (Self-contained in server.py)
# ==============================================================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cinema.db")

svg_icon = """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>
</svg>
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Movies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        year INTEGER,
        genre TEXT,
        runtime TEXT,
        synopsis TEXT,
        poster_url TEXT,
        screened_count INTEGER DEFAULT 0,
        suggested_by TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Ensure screened_count and suggested_by columns exist in existing database
    cursor.execute("PRAGMA table_info(movies)")
    cols = [col[1] for col in cursor.fetchall()]
    if "screened_count" not in cols:
        cursor.execute("ALTER TABLE movies ADD COLUMN screened_count INTEGER DEFAULT 0")
    if "suggested_by" not in cols:
        cursor.execute("ALTER TABLE movies ADD COLUMN suggested_by TEXT")

    # Votes table (one vote per member name per active session/event)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voter_name TEXT NOT NULL,
        movie_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE,
        UNIQUE(voter_name)
    )
    """)

    # Snack / Concession Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL, -- 'popcorn', 'drink', 'candy', 'combo'
        flavor TEXT,            -- 'Sweet', 'Salty', 'Caramel', etc.
        size TEXT,              -- 'Small', 'Medium', 'Large'
        price REAL NOT NULL,
        description TEXT,
        emoji TEXT,
        is_available INTEGER DEFAULT 1
    )
    """)

    # Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        total_price REAL NOT NULL,
        is_paid INTEGER DEFAULT 0,
        is_delivered INTEGER DEFAULT 0,
        payment_method TEXT DEFAULT 'carte',
        status TEXT DEFAULT 'pending', -- 'pending', 'preparing', 'ready', 'collected'
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Ensure orders columns exist in case table was created previously
    cursor.execute("PRAGMA table_info(orders)")
    existing_order_cols = {row["name"] for row in cursor.fetchall()}
    if "payment_method" not in existing_order_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'carte'")
    if "is_delivered" not in existing_order_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN is_delivered INTEGER DEFAULT 0")

    # Order items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    )
    """)

    # Letterboxd-style Reviews & Ratings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        reviewer_name TEXT NOT NULL,
        rating REAL NOT NULL, -- 1.0 to 5.0
        review_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE,
        UNIQUE(movie_id, reviewer_name)
    )
    """)

    # Wooclap-style Live Word Cloud table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS word_cloud (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER,
        contributor_name TEXT,
        word TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE
    )
    """)

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Screenings table (for movie history)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS screenings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        screening_date TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
    )
    """)

    # Seed admin account if not exists
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE username = 'admin'")
    if cursor.fetchone()["count"] == 0:
        admin_hash = hashlib.sha256("kinepolics2024".encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)", ("admin", admin_hash))

    # Seed initial data if empty
    cursor.execute("SELECT COUNT(*) as count FROM movies")
    if cursor.fetchone()["count"] == 0:
        seed_data(cursor)
    else:
        # Ensure products are synced to official KinepoliCS tariffs (visuals/2.png)
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE category = 'popcorn' AND size = 'Petit'")
        if cursor.fetchone()["count"] == 0:
            update_to_kinepolics_tarifs(cursor)

    # Sync movie suggestions from survey PDF with screened counts
    sync_kinepolics_movie_suggestions(cursor)

    # Seed initial screenings
    seed_initial_screenings(cursor)

    conn.commit()
    conn.close()

def get_kinepolics_products():
    return [
        ("Petit sucré", "popcorn", "Sucré", "Petit", 1.00, "", "🍿", 1),
        ("Petit salé", "popcorn", "Salé", "Petit", 1.00, "", "🍿", 1),
        ("Moyen sucré", "popcorn", "Sucré", "Moyen", 1.50, "", "🍿", 1),
        ("Moyen salé", "popcorn", "Salé", "Moyen", 1.50, "", "🍿", 1),
        ("Grand sucré", "popcorn", "Sucré", "Grand", 2.00, "", "🍿", 1),
        ("Grand salé", "popcorn", "Salé", "Grand", 2.00, "", "🍿", 1),
        ("Boisson 33cl", "drink", "Frais", "Canette", 1.50, "Coca, Ice Tea ou Eau", "🥤", 1),
    ]

def update_to_kinepolics_tarifs(cursor):
    cursor.execute("DELETE FROM products")
    cursor.executemany("""
    INSERT INTO products (name, category, flavor, size, price, description, emoji, is_available)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, get_kinepolics_products())

def seed_data(cursor):
    # Sample movie nominations
    movies = [
        (
            "Interstellar",
            2014,
            "Sci-Fi / Adventure",
            "2h 49m",
            "When Earth becomes uninhabitable in the future, a farmer and ex-NASA pilot is tasked to pilot a spacecraft along with a team of researchers to find a new planet for humans.",
            "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=600&auto=format&fit=crop&q=80",
            1
        ),
        (
            "Spirited Away",
            2001,
            "Animation / Fantasy",
            "2h 05m",
            "During her family's move to the suburbs, a sullen 10-year-old girl wanders into a world ruled by gods, witches and spirits, where humans are changed into beasts.",
            "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600&auto=format&fit=crop&q=80",
            1
        ),
        (
            "Spider-Man: Into the Spider-Verse",
            2018,
            "Action / Animation",
            "1h 57m",
            "Teen Miles Morales becomes the new Spider-Man and joins other Spider-Heroes from alternate dimensions to stop a threat for all realities.",
            "https://images.unsplash.com/photo-1635805737707-575885ab0820?w=600&auto=format&fit=crop&q=80",
            1
        ),
        (
            "La La Land",
            2016,
            "Comedy / Drama / Musical",
            "2h 08m",
            "While navigating their careers in Los Angeles, a pianist and an actress fall in love while attempting to reconcile their aspirations for the future.",
            "https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=600&auto=format&fit=crop&q=80",
            1
        )
    ]
    cursor.executemany("""
    INSERT INTO movies (title, year, genre, runtime, synopsis, poster_url, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, movies)

    # Official KinepoliCS Concessions & Popcorn Tarifs (visuals/2.png)
    cursor.executemany("""
    INSERT INTO products (name, category, flavor, size, price, description, emoji, is_available)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, get_kinepolics_products())

    # Seed sample Letterboxd reviews for Interstellar (movie 1) and Spirited Away (movie 2)
    reviews = [
        (1, "Clara_Cinephile", 5.0, "The docking scene with Zimmer's soundtrack in a lecture hall with friends gave me full-body chills! Absolute cinema masterpiece."),
        (1, "Thomas R.", 4.5, "Loved the scientific ambition and emotional father-daughter core. Tars is the real hero though."),
        (1, "Maya2004", 4.0, "A bit long in the middle act, but that black hole sequence on the big screen made it unforgettable."),
        (2, "StudioGhibliFan", 5.0, "Pure visual poetry. The train on the water scene will forever be one of the most serene moments in animation history.")
    ]
    cursor.executemany("""
    INSERT OR IGNORE INTO reviews (movie_id, reviewer_name, rating, review_text)
    VALUES (?, ?, ?, ?)
    """, reviews)

    # Seed sample Wooclap buzzwords for Interstellar (movie 1)
    words = [
        (1, "Lucas", "Masterpiece"), (1, "Sarah", "Masterpiece"), (1, "Amir", "Masterpiece"), (1, "Elena", "Masterpiece"),
        (1, "Alex", "Emotional"), (1, "Chloe", "Emotional"), (1, "David", "Emotional"),
        (1, "Lea", "Hans Zimmer"), (1, "Marc", "Hans Zimmer"), (1, "Sophie", "Hans Zimmer"),
        (1, "Nico", "Black Hole"), (1, "Julien", "Black Hole"),
        (1, "Tom", "Relativity"),
        (1, "Paul", "Goosebumps"), (1, "Sam", "Goosebumps"),
        (1, "Lina", "Epic"), (1, "Romain", "Epic"), (1, "Zoé", "Epic"), (1, "Théo", "Epic"),
        (1, "Anna", "Cosmic"), (1, "Max", "Tears")
    ]
    cursor.executemany("""
    INSERT INTO word_cloud (movie_id, contributor_name, word)
    VALUES (?, ?, ?)
    """, words)

def get_kinepolics_movie_suggestions():
    return [
        # Films cultes
        ("Interstellar", 2014, "Films cultes", "2h 49m", "Une équipe d'explorateurs voyage à travers un trou de ver pour assurer la survie de l'humanité.", "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=600", 2),
        ("Fight Club", 1999, "Films cultes", "2h 19m", "Un employé insomniaque et un fabriquant de savon charismatique créent un club de combat clandestin.", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600", 1),
        ("Whiplash", 2014, "Films cultes", "1h 47m", "Un jeune batteur de jazz intègre un conservatoire d'élite dirigé par un professeur impitoyable.", "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600", 1),
        ("Parasite", 2019, "Films cultes", "2h 12m", "Toute la famille de Ki-taek est au chômage jusqu'au jour où le fils réussit à se faire embaucher chez les riches Park.", "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600", 1),
        ("Joker", 2019, "Films cultes", "2h 02m", "Arthur Fleck bascule peu à peu dans la folie pour devenir le criminel le plus célèbre de Gotham.", "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=600", 1),
        ("Pulp Fiction", 1994, "Films cultes", "2h 34m", "L'odyssée sanglante et burlesque de petits malfrats dans la jungle de Hollywood.", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600", 1),
        ("Oppenheimer", 2023, "Films cultes", "3h 00m", "Le physicien J. Robert Oppenheimer dirige le projet Manhattan pour concevoir la première bombe atomique.", "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=600", 0),
        ("Shutter Island", 2010, "Films cultes", "2h 18m", "Deux marshals enquêtent sur la disparition d'une patiente dans un hôpital psychiatrique insulaire.", "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600", 0),
        ("Bullet Train", 2022, "Films cultes", "2h 06m", "Cinq assassins se retrouvent à bord d'un train à grande vitesse reliant Tokyo à Kyoto.", "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=600", 0),
        ("Inception", 2010, "Films cultes", "2h 28m", "Un voleur expérimenté s'infiltre dans les rêves pour y dérober ou implanter des secrets.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", 0),
        ("Blade Runner", 1982, "Films cultes", "1h 57m", "Dans un Los Angeles dystopique, un policier traque des androïdes déclarés hors-la-loi.", "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600", 0),
        ("Chungking Express", 1994, "Films cultes", "1h 42m", "Deux policiers hongkongais vivent des histoires d'amour éphémères et poétiques.", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600", 0),
        ("Le Parrain", 1972, "Films cultes", "2h 55m", "L'ascension et la chute d'une puissante famille de la mafia italo-américaine à New York.", "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=600", 0),
        ("Le Loup de Wall Street", 2013, "Films cultes", "3h 00m", "L'ascension fulgurante et les excès vertigineux d'un courtier en bourse new-yorkais.", "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=600", 0),
        ("The Truman Show", 1998, "Films cultes", "1h 43m", "Truman Burbank découvre que toute sa vie n'est qu'une émission de téléréalité filmée 24h/24.", "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600", 0),
        ("L'Amour ouf", 2024, "Films cultes", "2h 46m", "Deux adolescents issus de milieux opposés tombent éperdument amoureux malgré les épreuves.", "https://images.unsplash.com/photo-1518199266791-5375a83190b7?w=600", 0),
        ("Seul sur Mars", 2015, "Films cultes", "2h 24m", "Laissé pour mort sur Mars, un astronaute tente de survivre avec d'ingénieux moyens.", "https://images.unsplash.com/photo-1614728894747-a83421e2b9c9?w=600", 0),
        ("Hunger Games", 2012, "Films cultes", "2h 22m", "Katniss Everdeen se porte volontaire pour remplacer sa sœur dans un jeu télévisé mortel.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", 0),
        ("Star Wars : Rogue One", 2016, "Films cultes", "2h 13m", "Un groupe de rebelles s'organise pour voler les plans de l'Étoile de la Mort.", "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?w=600", 0),
        ("Pirates des Caraïbes", 2003, "Films cultes", "2h 23m", "Le capitaine Jack Sparrow s'associe à un forgeron pour sauver la fille du gouverneur.", "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=600", 0),

        # Horreur
        ("Hereditary", 2018, "Horreur", "2h 07m", "Après le décès de leur grand-mère, une famille découvre de terrifiants secrets ancestraux.", "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=600", 1),
        ("Conjuring", 2013, "Horreur", "1h 52m", "Les chasseurs de fantômes Ed et Lorraine Warren viennent en aide à une famille terrorisée.", "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=600", 0),
        ("The Blair Witch Project", 1999, "Horreur", "1h 21m", "Trois étudiants en cinéma disparaissent dans une forêt réputée hantée.", "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600", 0),
        ("Sans un bruit", 2018, "Horreur", "1h 30m", "Une famille doit vivre dans le silence le plus absolu pour échapper à des créatures aveugles.", "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=600", 0),
        ("Le Silence des agneaux", 1991, "Horreur", "1h 58m", "Clarice Starling consulte le Dr Hannibal Lecter pour traquer un tueur en série.", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600", 0),
        ("The Perfection", 2018, "Horreur", "1h 30m", "Une violoncelliste prodigieuse renoue avec ses anciens mentors, déclenchant une spirale de vengeance.", "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600", 0),

        # Animation
        ("L'Île aux chiens", 2018, "Animation", "1h 41m", "Au Japon, tous les chiens de Megasaki sont bannis sur une île-poubelle. Un jeune garçon part à leur recherche.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", 1),
        ("Azur et Asmar", 2006, "Animation", "1h 39m", "Deux frères de lait élevés ensemble partent chacun de leur côté à la recherche de la Fée des Djinns.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", 1),
        ("Kirikou et la Sorcière", 1998, "Animation", "1h 11m", "Le minuscule Kirikou naît dans un village africain sur lequel la terrible sorcière Karaba a jeté un sort.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", 1),
        ("Le Voyage de Chihiro", 2001, "Animation", "2h 05m", "Une fillette de 10 ans pénètre dans un monde enchanté gouverné par une sorcière et des esprits.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", 1),
        ("Princesse Mononoké", 1997, "Animation", "2h 14m", "Un prince frappé d'une malédiction cherche l'apaisement entre les esprits de la forêt et les forgerons.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", 0),
        ("Le Château ambulant", 2004, "Animation", "1h 59m", "Sophie est transformée en vieille femme et trouve refuge dans le château magique du magicien Hauru.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", 0),
        ("Le Roi et l'Oiseau", 1980, "Animation", "1h 23m", "Chef-d'œuvre poétique de Paul Grimault d'après Hans Christian Andersen.", "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600", 0),
        ("La Grande Aventure Lego", 2014, "Animation", "1h 40m", "Une figurine ordinaire est prise par erreur pour l'élu capable de sauver l'univers Lego.", "https://images.unsplash.com/photo-1585366119957-e9730b6d0f60?w=600", 0),

        # Drames
        ("Le Cercle des poètes disparus", 1989, "Drames", "2h 08m", "Un professeur de lettres peu conventionnel éveille ses élèves à la liberté de penser et à la poésie.", "https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=600", 1),
        ("Slumdog Millionaire", 2008, "Drames", "2h 00m", "Un jeune orphelin des bidonvilles de Mumbai participe au jeu Qui veut gagner des millions ?.", "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=600", 0),
        ("12 Hommes en colère", 1957, "Drames", "1h 36m", "Douze jurés délibèrent sur le sort d'un jeune homme accusé de parricide.", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600", 0),
        ("Les Évadés (The Shawshank Redemption)", 1994, "Drames", "2h 22m", "Condamné à tort pour le meurtre de sa femme, Andy Dufresne garde espoir au pénitencier de Shawshank.", "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600", 0),
        ("La vie est belle", 1997, "Drames", "1h 56m", "Un père use d'imagination et d'humour pour protéger son fils des horreurs d'un camp de concentration.", "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=600", 0),
        ("Gatsby le Magnifique", 2013, "Drames", "2h 22m", "L'histoire d'un mystérieux millionnaire qui organise de somptueuses fêtes pour reconquérir son amour de jeunesse.", "https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=600", 0),

        # Action
        ("Kill Bill (Vol. 1 & 2)", 2003, "Action", "1h 51m", "Une ancienne tueuse à gages sort du coma et se lance dans une impitoyable vendetta contre ses anciens associés.", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600", 0),
        ("Pacific Rim", 2013, "Action", "2h 11m", "Pour affronter de gigantesques monstres marins, l'humanité conçoit des robots colossaux pilotés par deux personnes.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", 0),
        ("American Sniper", 2014, "Action", "2h 13m", "Le tireur d'élite le plus redoutable des Navy SEALs tente de préserver sa vie de famille entre chaque mission.", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600", 0),

        # Comédie
        ("Astérix & Obélix : Mission Cléopâtre", 2002, "Comédie", "1h 47m", "Pour séduire César, Cléopâtre fait appel à l'architecte Numérobis, aidé des célèbres Gaulois et de leur potion magique.", "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=600", 0),
        ("La Cité de la peur", 1994, "Comédie", "1h 39m", "Pendant le Festival de Cannes, un tueur élimine des projectionnistes avec une faucille et un marteau.", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600", 0),
        ("La Tour Montparnasse infernale", 2001, "Comédie", "1h 32m", "Deux laveurs de carreaux se retrouvent piégés dans la tour Montparnasse face à un commando de terroristes.", "https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=600", 0),
        ("The Dictator", 2012, "Comédie", "1h 23m", "Le général Aladeen risque sa vie pour s'assurer que la démocratie ne verra jamais le jour dans son pays.", "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=600", 0),

        # Comédie musicale
        ("La La Land", 2016, "Comédie musicale", "2h 08m", "À Los Angeles, un pianiste de jazz passionné et une actrice débutante tombent éperdument amoureux.", "https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=600", 1),
        ("West Side Story", 2021, "Comédie musicale", "2h 36m", "Dans le New York des années 1950, deux bandes rivales s'affrontent tandis qu'une romance naît entre deux jeunes.", "https://images.unsplash.com/photo-1514306191717-452ec28c7814?w=600", 0),

        # Fantasy & Sci-Fi
        ("Le Seigneur des Anneaux : La Trilogie", 2001, "Fantasy & Sci-Fi", "3h 28m", "Frodon Sacquet entreprend un périlleux voyage pour détruire l'Anneau Unique au cœur de la Montagne du Destin.", "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600", 0),
        ("Snowpiercer", 2013, "Fantasy & Sci-Fi", "2h 06m", "Dans un train géant condamné à tourner indéfiniment autour d'une Terre glacée, la révolte gronde dans les wagons de queue.", "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=600", 0),
        ("Gravity", 2013, "Fantasy & Sci-Fi", "1h 31m", "Deux astronautes se retrouvent isolés dans le vide spatial après la destruction de leur navette.", "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?w=600", 0),

        # Romance
        ("In the Mood for Love", 2000, "Romance", "1h 38m", "À Hong Kong en 1962, deux voisins découvrent que leurs conjoints respectifs ont une liaison.", "https://images.unsplash.com/photo-1518199266791-5375a83190b7?w=600", 0),
        ("Titanic", 1997, "Romance", "3h 14m", "L'amour passionné entre Jack et Rose à bord du paquebot insubmersible lors de sa traversée inaugurale.", "https://images.unsplash.com/photo-1518199266791-5375a83190b7?w=600", 0),
    ]

def sync_kinepolics_movie_suggestions(cursor):
    cursor.execute("SELECT LOWER(title) FROM movies")
    existing_titles = {row[0] for row in cursor.fetchall()}

    for title, year, genre, runtime, synopsis, poster, screened_count in get_kinepolics_movie_suggestions():
        if title.lower() not in existing_titles:
            cursor.execute("""
            INSERT INTO movies (title, year, genre, runtime, synopsis, poster_url, screened_count, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (title, year, genre, runtime, synopsis, poster, screened_count))
        else:
            # Update screened_count if it was 0 and we have a positive count from the survey
            if screened_count > 0:
                cursor.execute("""
                UPDATE movies SET screened_count = ? WHERE LOWER(title) = ? AND (screened_count = 0 OR screened_count IS NULL)
                """, (screened_count, title.lower()))

def seed_initial_screenings(cursor):
    """Seed the screenings table with historical projection data."""
    cursor.execute("SELECT COUNT(*) as count FROM screenings")
    if cursor.fetchone()["count"] > 0:
        return  # Already seeded

    historical = [
        ("Parasite", "03/10/25"),
        ("Le Cercle des poètes disparus", "10/10/25"),  # was "Dead Poets Society" in English
        ("L'Île aux chiens", "15/10/25"),  # was "Isle of dogs"
        ("Whiplash", "20/10/25"),
        ("Hunger Games", "21/11/25"),
        ("Azur et Asmar", ""),
        ("Blade Runner", ""),
        ("Mickey 17", ""),  # was "Mickey 17" but probably meant another
        ("Frankenstein", "2025"),  # not in DB yet — skip if not found
        ("Le Roi et l'Oiseau", ""),
        ("The Cube", ""),  # was "The Cube" — use closest match
        ("Don't Look Up", ""),  # was "Don't Look Up" 
    ]

    for title, date in historical:
        cursor.execute("SELECT id FROM movies WHERE LOWER(title) LIKE LOWER(?)", (f"%{title}%",))
        row = cursor.fetchone()
        if row:
            cursor.execute("INSERT INTO screenings (movie_id, screening_date) VALUES (?, ?)", (row["id"], date))

# ==============================================================================
# HTTP REQUEST HANDLER & REST API
# ==============================================================================
class CinemaRequestHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Pin")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def parse_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def get_current_user(self):
        """Extract user from Authorization header. Returns dict with id, username, is_admin or None."""
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        try:
            decoded = base64.b64decode(token).decode("utf-8")
            username, password_hash = decoded.split(":", 1)
        except Exception:
            return None
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, is_admin, password_hash FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and user["password_hash"] == password_hash:
            return {"id": user["id"], "username": user["username"], "is_admin": bool(user["is_admin"])}
        return None

    def require_admin(self):
        """Check if current user is admin. Sends 401/403 and returns None if not. Returns user dict if admin."""
        user = self.get_current_user()
        if not user:
            self.send_json({"error": "Authentification requise."}, 401)
            return None
        if not user["is_admin"]:
            self.send_json({"error": "Accès réservé aux administrateurs."}, 403)
            return None
        return user

    def check_admin_auth(self):
        # Try new user-based auth first
        user = self.get_current_user()
        if user and user["is_admin"]:
            return True
        # Fallback to PIN header
        pin = self.headers.get("X-Admin-Pin", "")
        return pin == ADMIN_PIN

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # API Routes
        if path == "/api/movies":
            self.handle_get_movies()
        elif path == "/api/tmdb/search":  # <-- AJOUTER CETTE ROUTE
            query_str = query.get("query", [""])[0]
            self.handle_get_tmdb_search(query_str)
        elif path == "/api/products":
            self.handle_get_products()
        elif path == "/api/orders":
            customer = query.get("customer", [None])[0]
            self.handle_get_orders(customer_name=customer)
        elif path.startswith("/api/orders/"):
            code_or_id = path[len("/api/orders/"):]
            self.handle_get_single_order(code_or_id)
        elif path == "/api/admin/stats":
            self.handle_get_admin_stats()
        elif path == "/api/admin/verify":
            # Quick PIN check
            pin = query.get("pin", [""])[0]
            self.send_json({"valid": pin == ADMIN_PIN})
        elif path == "/api/reviews":
            movie_id = query.get("movie_id", [None])[0]
            self.handle_get_reviews(movie_id)
        elif path == "/api/wordcloud":
            movie_id = query.get("movie_id", [None])[0]
            self.handle_get_wordcloud(movie_id)
        elif path == "/api/auth/me":
            self.handle_auth_me()
        elif path == "/api/stats/leaderboard":
            self.handle_get_leaderboard()
        elif path == "/api/history":
            self.handle_get_history()
        else:
            # Serve static files
            self.serve_static(path)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/auth/register":
            self.handle_auth_register()
        elif path == "/api/auth/login":
            self.handle_auth_login()
        elif path.startswith("/api/admin/movies/") and path.endswith("/to-history"):
            admin = self.require_admin()
            if not admin:
                return
            parts = path.split("/")
            movie_id = parts[4]  # /api/admin/movies/{id}/to-history
            self.handle_admin_move_to_history(movie_id)
        elif path == "/api/admin/products":
            admin = self.require_admin()
            if not admin:
                return
            self.handle_admin_add_product()
        elif path == "/api/vote":
            self.handle_post_vote()
        elif path in ("/api/movies/suggest", "/api/movies"):
            self.handle_post_suggest_movie()
        elif path.startswith("/api/movies/") and path.endswith("/screened"):
            parts = path.strip("/").split("/")
            if len(parts) >= 3:
                self.handle_post_increment_screened(parts[2])
            else:
                self.send_json({"error": "Invalid URL"}, 400)
        elif path == "/api/orders":
            self.handle_post_order()
        elif path == "/api/reviews":
            self.handle_post_review()
        elif path == "/api/wordcloud":
            self.handle_post_wordcloud()
        elif path == "/api/admin/movies":
            if not self.check_admin_auth():
                return self.send_json({"error": "Unauthorized. Invalid Admin PIN."}, 401)
            self.handle_admin_add_movie()
        elif path == "/api/admin/reset":
            if not self.check_admin_auth():
                return self.send_json({"error": "Unauthorized. Invalid Admin PIN."}, 401)
            self.handle_admin_reset()
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    def do_PATCH(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/orders/"):
            order_id = path[len("/api/orders/"):]
            self.handle_patch_order(order_id)
        elif path.startswith("/api/admin/products/"):
            admin = self.require_admin()
            if not admin:
                return
            product_id = path[len("/api/admin/products/"):]
            self.handle_admin_update_product(product_id)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/orders/"):
            order_id = path[len("/api/orders/"):]
            self.handle_delete_order(order_id)
        elif path.startswith("/api/reviews/"):
            review_id = path[len("/api/reviews/"):]
            self.handle_delete_review(review_id)
        elif path.startswith("/api/wordcloud/"):
            word_id = path[len("/api/wordcloud/"):]
            self.handle_delete_wordcloud(word_id)
        elif path.startswith("/api/admin/products/"):
            admin = self.require_admin()
            if not admin:
                return
            product_id = path[len("/api/admin/products/"):]
            self.handle_admin_delete_product(product_id)
        elif path.startswith("/api/admin/movies/"):
            if not self.check_admin_auth():
                return self.send_json({"error": "Unauthorized. Invalid Admin PIN."}, 401)
            movie_id = path[len("/api/admin/movies/"):]
            self.handle_admin_delete_movie(movie_id)
        else:
            self.send_json({"error": "Endpoint not found"}, 404)

    # ----------------- Movie & Voting Handlers -----------------

    def handle_get_movies(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        genre = qs.get("genre", [None])[0]
        screened = qs.get("screened", [None])[0]
        search = qs.get("search", [None])[0]

        conn = get_db()
        cursor = conn.cursor()

        where_clauses = ["m.is_active = 1"]
        params = []

        if genre and genre.lower() not in ("all", "tous"):
            where_clauses.append("LOWER(m.genre) LIKE ?")
            params.append(f"%{genre.lower()}%")

        if screened in ("true", "yes", "1"):
            where_clauses.append("m.screened_count > 0")
        elif screened in ("false", "no", "0"):
            where_clauses.append("(m.screened_count = 0 OR m.screened_count IS NULL)")

        if search:
            where_clauses.append("(LOWER(m.title) LIKE ? OR LOWER(m.synopsis) LIKE ?)")
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])

        sql = f"""
            SELECT m.*, 
                   COUNT(v.id) AS vote_count
            FROM movies m
            LEFT JOIN votes v ON m.id = v.movie_id
            WHERE {" AND ".join(where_clauses)}
            GROUP BY m.id
            ORDER BY vote_count DESC, m.screened_count DESC, m.title ASC
        """
        cursor.execute(sql, params)
        movies = [dict(row) for row in cursor.fetchall()]
        
        # Calculate total votes
        total_votes = sum(m["vote_count"] for m in movies)
        for m in movies:
            m["percentage"] = round((m["vote_count"] / total_votes * 100), 1) if total_votes > 0 else 0

        # Unique genre list
        cursor.execute("SELECT DISTINCT genre FROM movies WHERE is_active = 1 AND genre IS NOT NULL")
        genres = [r["genre"] for r in cursor.fetchall() if r["genre"]]

        conn.close()
        self.send_json({
            "movies": movies,
            "total_votes": total_votes,
            "genres": genres
        })

    def handle_get_tmdb_search(self, query):
            """Recherche en direct sur TMDB pour l'autocomplétion de la modale."""
            if not query or len(query.strip()) < 2:
                return self.send_json({"results": []})

            if not TMDB_API_KEY or TMDB_API_KEY == "TA_CLE_API_TMDB_ICI":
                return self.send_json({"results": []})

            try:
                encoded_query = urllib.parse.quote(query.strip())
                url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={encoded_query}&language=fr-FR"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    raw_results = data.get("results", [])[:5]  # Limiter aux 5 premiers candidats

                    candidates = []
                    for m in raw_results:
                        poster_path = m.get("poster_path")
                        release_date = m.get("release_date", "")
                        year = int(release_date.split("-")[0]) if release_date and len(release_date) >= 4 else None

                        candidates.append({
                            "id": m.get("id"),
                            "title": m.get("title") or m.get("original_title"),
                            "year": year,
                            "synopsis": m.get("overview") or "Aucun synopsis disponible.",
                            "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600"
                        })

                    return self.send_json({"results": candidates})
            except Exception as e:
                print(f"Erreur recherche TMDB : {e}")
                return self.send_json({"results": []})

    def handle_post_suggest_movie(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Corps JSON invalide"}, 400)

        title = str(data.get("title", "")).strip()
        if not title:
            return self.send_json({"error": "Le titre du film est obligatoire."}, 400)

        suggested_by = str(data.get("suggested_by", "")).strip() or None
        year = data.get("year")
        synopsis = str(data.get("synopsis", "Aucun synopsis disponible.")).strip()
        poster_url = str(data.get("poster_url", "")).strip() or "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600"

        conn = get_db()
        cursor = conn.cursor()

        # Vérifier si le film existe déjà en BDD
        cursor.execute("SELECT id, title FROM movies WHERE LOWER(title) = LOWER(?)", (title,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return self.send_json({
                "success": False,
                "already_exists": True,
                "message": f"« {existing['title']} » est déjà dans la liste des suggestions !"
            }, 200)

        cursor.execute("""
            INSERT INTO movies (title, year, genre, runtime, synopsis, poster_url, screened_count, suggested_by, is_active)
            VALUES (?, ?, 'Films cultes', '2h 00m', ?, ?, 0, ?, 1)
        """, (title, year, synopsis, poster_url, suggested_by))

        conn.commit()
        movie_id = cursor.lastrowid
        conn.close()

        self.send_json({
            "success": True,
            "movie_id": movie_id,
            "message": f"✨ « {title} » a été ajouté aux suggestions !"
        }, 201)

    def handle_post_vote(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid JSON body"}, 400)

        voter_name = str(data.get("voter_name", "")).strip()
        movie_id = data.get("movie_id")

        if not voter_name:
            return self.send_json({"error": "Please enter your name or username to vote."}, 400)
        if not movie_id:
            return self.send_json({"error": "Please select a movie to vote for."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        # Check if user already voted
        cursor.execute("SELECT id, movie_id FROM votes WHERE LOWER(voter_name) = LOWER(?)", (voter_name,))
        existing_vote = cursor.fetchone()

        if existing_vote:
            # Change vote or prevent? Let's allow changing vote with clear message
            cursor.execute("UPDATE votes SET movie_id = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?", 
                        (movie_id, existing_vote["id"]))
            conn.commit()
            conn.close()
            return self.send_json({
                "success": True,
                "message": f"Your vote has been updated for '{voter_name}'!",
                "updated": True
            })
        else:
            cursor.execute("INSERT INTO votes (voter_name, movie_id) VALUES (?, ?)", (voter_name, movie_id))
            conn.commit()
            conn.close()
            return self.send_json({
                "success": True,
                "message": f"Thank you, {voter_name}! Your vote has been recorded.",
                "updated": False
            })

    # ----------------- Snack Products & Orders Handlers -----------------

    def handle_get_products(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE is_available = 1 ORDER BY category ASC, price ASC")
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        self.send_json({"products": products})

    def handle_post_order(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid request body"}, 400)

        customer_name = str(data.get("customer_name", "")).strip()
        items = data.get("items", [])
        notes = data.get("notes", "")
        payment_method = str(data.get("payment_method", "carte")).strip().lower()
        if payment_method not in ("carte", "especes", "sumup"):
            payment_method = "carte"

        if not customer_name:
            return self.send_json({"error": "Please provide your name for order pickup."}, 400)
        if not items or len(items) == 0:
            return self.send_json({"error": "Your cart is empty."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        # Calculate exact total from database to prevent price manipulation
        total_price = 0.0
        validated_items = []
        for it in items:
            p_id = it.get("product_id")
            qty = int(it.get("quantity", 1))
            if qty <= 0:
                continue
            cursor.execute("SELECT * FROM products WHERE id = ? AND is_available = 1", (p_id,))
            prod = cursor.fetchone()
            if prod:
                item_total = prod["price"] * qty
                total_price += item_total
                validated_items.append({
                    "product_id": prod["id"],
                    "product_name": prod["name"],
                    "quantity": qty,
                    "unit_price": prod["price"]
                })

        if not validated_items:
            conn.close()
            return self.send_json({"error": "No valid products found in cart."}, 400)

        # Generate friendly order code, e.g. POP-492
        num = random.randint(100, 999)
        order_code = f"POP-{num}"

        # Insert order
        cursor.execute("""
            INSERT INTO orders (order_code, customer_name, total_price, is_paid, status, notes)
            VALUES (?, ?, ?, 0, 'pending', ?)
        """, (order_code, customer_name, round(total_price, 2), notes))
        order_id = cursor.lastrowid

        # Insert order items
        for it in validated_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, it["product_id"], it["product_name"], it["quantity"], it["unit_price"]))

        conn.commit()
        conn.close()

        self.send_json({
            "success": True,
            "order": {
                "id": order_id,
                "order_code": order_code,
                "customer_name": customer_name,
                "total_price": round(total_price, 2),
                "status": "pending",
                "is_paid": 0,
                "is_delivered": 0,
                "payment_method": payment_method,
                "items": validated_items
            }
        }, 201)

    def handle_get_orders(self, customer_name=None):
        conn = get_db()
        cursor = conn.cursor()

        if customer_name:
            cursor.execute("""
                SELECT * FROM orders 
                WHERE LOWER(customer_name) = LOWER(?) 
                ORDER BY created_at DESC
            """, (customer_name.strip(),))
        else:
            cursor.execute("SELECT * FROM orders ORDER BY id DESC")

        orders = [dict(row) for row in cursor.fetchall()]

        # Fetch items for each order
        for ord_obj in orders:
            cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (ord_obj["id"],))
            ord_obj["items"] = [dict(it) for it in cursor.fetchall()]

        conn.close()
        self.send_json({"orders": orders})

    def handle_get_single_order(self, code_or_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_code = ? OR id = ?", (code_or_id, code_or_id))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return self.send_json({"error": "Order not found"}, 404)

        order_data = dict(order)
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_data["id"],))
        order_data["items"] = [dict(it) for it in cursor.fetchall()]
        conn.close()
        self.send_json({"order": order_data})

    def handle_patch_order(self, order_id):
        data = self.parse_json_body()
        if data is None:
            return self.send_json({"error": "Invalid request body"}, 400)

        conn = get_db()
        cursor = conn.cursor()

        updates = []
        params = []
        if "is_paid" in data:
            updates.append("is_paid = ?")
            params.append(1 if data["is_paid"] else 0)
        if "is_delivered" in data:
            updates.append("is_delivered = ?")
            params.append(1 if data["is_delivered"] else 0)
        if "status" in data:
            updates.append("status = ?")
            params.append(str(data["status"]))
        if "payment_method" in data:
            updates.append("payment_method = ?")
            params.append(str(data["payment_method"]))

        if not updates:
            conn.close()
            return self.send_json({"error": "No fields to update"}, 400)

        params.append(order_id)
        query = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        updated_row = cursor.fetchone()
        conn.close()

        if not updated_row:
            return self.send_json({"error": "Order not found"}, 404)

        self.send_json({"success": True, "order": dict(updated_row)})

    def handle_delete_order(self, order_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Order deleted."})

    # ----------------- Admin Analytics & Management -----------------

    def handle_get_admin_stats(self):
        conn = get_db()
        cursor = conn.cursor()

        # Unique voters
        cursor.execute("SELECT DISTINCT LOWER(voter_name) as name FROM votes")
        voters = {row["name"] for row in cursor.fetchall()}

        # Unique snack buyers
        cursor.execute("SELECT DISTINCT LOWER(customer_name) as name FROM orders")
        buyers = {row["name"] for row in cursor.fetchall()}

        # Unique total attendees (voters union buyers)
        attendees = voters.union(buyers)

        # Revenue totals
        cursor.execute("SELECT SUM(total_price) as total_rev, COUNT(id) as total_orders FROM orders")
        rev_row = cursor.fetchone()
        total_revenue = rev_row["total_rev"] or 0.0
        total_orders = rev_row["total_orders"] or 0

        cursor.execute("SELECT SUM(total_price) as paid_rev FROM orders WHERE is_paid = 1")
        paid_row = cursor.fetchone()
        paid_revenue = paid_row["paid_rev"] or 0.0

        # Total votes
        cursor.execute("SELECT COUNT(id) as total_votes FROM votes")
        total_votes = cursor.fetchone()["total_votes"]

        # Popular snack items
        cursor.execute("""
            SELECT product_name, SUM(quantity) as total_qty, SUM(quantity * unit_price) as total_item_rev
            FROM order_items
            GROUP BY product_name
            ORDER BY total_qty DESC
            LIMIT 5
        """)
        top_snacks = [dict(row) for row in cursor.fetchall()]

        # Orders summary status
        cursor.execute("SELECT status, COUNT(id) as count FROM orders GROUP BY status")
        order_status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

        conn.close()

        self.send_json({
            "total_attendees": len(attendees),
            "unique_voters": len(voters),
            "unique_buyers": len(buyers),
            "total_votes": total_votes,
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "paid_revenue": round(paid_revenue, 2),
            "unpaid_revenue": round(total_revenue - paid_revenue, 2),
            "top_snacks": top_snacks,
            "order_status_counts": order_status_counts
        })

    def handle_admin_add_movie(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid request body"}, 400)

        title = str(data.get("title", "")).strip()
        if not title:
            return self.send_json({"error": "Movie title is required."}, 400)

        year = int(data.get("year", 2024))
        genre = str(data.get("genre", "Cinema Selection"))
        runtime = str(data.get("runtime", "2h 00m"))
        synopsis = str(data.get("synopsis", "Candidate film for the upcoming student movie night."))
        poster_url = str(data.get("poster_url", "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=600&auto=format&fit=crop&q=80"))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO movies (title, year, genre, runtime, synopsis, poster_url, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (title, year, genre, runtime, synopsis, poster_url))
        conn.commit()
        movie_id = cursor.lastrowid
        conn.close()

        self.send_json({"success": True, "movie_id": movie_id, "message": f"Added '{title}' to nominations!"}, 201)

    def handle_admin_delete_movie(self, movie_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Movie removed from nominations."})

    def handle_admin_reset(self):
        conn = get_db()
        cursor = conn.cursor()
        # Reset votes, orders, reviews and word clouds for a brand new movie night
        cursor.execute("DELETE FROM votes")
        cursor.execute("DELETE FROM order_items")
        cursor.execute("DELETE FROM orders")
        cursor.execute("DELETE FROM reviews")
        cursor.execute("DELETE FROM word_cloud")
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Movie night reset successfully! Votes, orders, reviews, and word cloud cleared."})

    # ----------------- Letterboxd-style Reviews Handlers -----------------

    def handle_get_reviews(self, movie_id=None):
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT r.*, m.title as movie_title, m.poster_url as movie_poster
            FROM reviews r
            JOIN movies m ON r.movie_id = m.id
        """
        params = []
        if movie_id:
            query += " WHERE r.movie_id = ?"
            params.append(movie_id)
        
        query += " ORDER BY r.created_at DESC"
        cursor.execute(query, params)
        reviews = [dict(row) for row in cursor.fetchall()]

        # Calculate average rating & star distribution
        avg_rating = 0.0
        total_reviews = len(reviews)
        star_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}

        if total_reviews > 0:
            total_score = sum(r["rating"] for r in reviews)
            avg_rating = round(total_score / total_reviews, 1)
            for r in reviews:
                rounded_star = min(5, max(1, round(r["rating"])))
                star_counts[rounded_star] = star_counts.get(rounded_star, 0) + 1

        conn.close()
        self.send_json({
            "reviews": reviews,
            "total_reviews": total_reviews,
            "avg_rating": avg_rating,
            "star_distribution": star_counts
        })

    def handle_post_review(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid JSON body"}, 400)

        reviewer_name = str(data.get("reviewer_name", "")).strip()
        movie_id = data.get("movie_id")
        try:
            rating = float(data.get("rating", 5.0))
        except (ValueError, TypeError):
            rating = 5.0

        review_text = str(data.get("review_text", "")).strip()

        if not reviewer_name:
            return self.send_json({"error": "Please enter your name or nickname."}, 400)
        if not movie_id:
            return self.send_json({"error": "Movie ID is required."}, 400)
        if rating < 0.5 or rating > 5.0:
            return self.send_json({"error": "Rating must be between 1 and 5 stars."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        # Check if user already reviewed this movie, update if so
        cursor.execute("SELECT id FROM reviews WHERE movie_id = ? AND LOWER(reviewer_name) = LOWER(?)", 
                       (movie_id, reviewer_name))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE reviews 
                SET rating = ?, review_text = ?, created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (rating, review_text, existing["id"]))
            conn.commit()
            review_id = existing["id"]
            updated = True
        else:
            cursor.execute("""
                INSERT INTO reviews (movie_id, reviewer_name, rating, review_text)
                VALUES (?, ?, ?, ?)
            """, (movie_id, reviewer_name, rating, review_text))
            conn.commit()
            review_id = cursor.lastrowid
            updated = False

        conn.close()
        self.send_json({
            "success": True,
            "review_id": review_id,
            "updated": updated,
            "message": "Review updated!" if updated else "Review posted! Thanks for your thoughts."
        }, 201)

    def handle_delete_review(self, review_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Review deleted."})

    # ----------------- Wooclap-style Word Cloud Handlers -----------------

    def handle_get_wordcloud(self, movie_id=None):
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT LOWER(TRIM(word)) as clean_word,
                   MAX(word) as display_word,
                   COUNT(id) as count
            FROM word_cloud
        """
        params = []
        if movie_id:
            query += " WHERE movie_id = ?"
            params.append(movie_id)

        query += " GROUP BY clean_word ORDER BY count DESC, clean_word ASC LIMIT 80"
        cursor.execute(query, params)
        raw_words = cursor.fetchall()

        words = []
        for row in raw_words:
            words.append({
                "word": row["display_word"],
                "count": row["count"]
            })

        total_submissions = sum(w["count"] for w in words)
        conn.close()

        self.send_json({
            "words": words,
            "total_submissions": total_submissions
        })

    def handle_post_wordcloud(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Invalid request body"}, 400)

        word = str(data.get("word", "")).strip()
        movie_id = data.get("movie_id")
        contributor = str(data.get("contributor_name", "Anonymous")).strip()

        # Clean word (strip basic punctuation, cap at 35 chars)
        word = word.strip(" !.,?\"'#:;~*&^%$@()[]{}").strip()
        if not word:
            return self.send_json({"error": "Please enter a word or feeling."}, 400)
        if len(word) > 40:
            return self.send_json({"error": "Keep it punchy (under 40 characters)!"}, 400)

        # Title-case single words or short phrases for clean visual cloud
        if len(word.split()) <= 2:
            display_word = word.title()
        else:
            display_word = word

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO word_cloud (movie_id, contributor_name, word)
            VALUES (?, ?, ?)
        """, (movie_id, contributor, display_word))
        conn.commit()
        word_id = cursor.lastrowid
        conn.close()

        self.send_json({
            "success": True,
            "word_id": word_id,
            "word": display_word,
            "message": f"'{display_word}' added to the live word cloud!"
        }, 201)

    def handle_delete_wordcloud(self, word_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM word_cloud WHERE id = ?", (word_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Word removed."})

    # ----------------- Auth Handlers -----------------

    def handle_auth_register(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Corps JSON invalide."}, 400)

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))

        if not username or len(username) < 2:
            return self.send_json({"error": "Le pseudo doit faire au moins 2 caractères."}, 400)
        if len(username) > 30:
            return self.send_json({"error": "Le pseudo ne peut pas dépasser 30 caractères."}, 400)
        if not password or len(password) < 4:
            return self.send_json({"error": "Le mot de passe doit faire au moins 4 caractères."}, 400)

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        token = base64.b64encode(f"{username}:{password_hash}".encode()).decode()

        conn = get_db()
        cursor = conn.cursor()

        # Check if username taken
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        if cursor.fetchone():
            conn.close()
            return self.send_json({"error": "Ce pseudo est déjà pris."}, 409)

        cursor.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)", (username, password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        self.send_json({
            "success": True,
            "token": token,
            "user": {"id": user_id, "username": username, "is_admin": False},
            "message": f"Bienvenue {username} ! Votre compte a été créé."
        }, 201)

    def handle_auth_login(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Corps JSON invalide."}, 400)

        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))

        if not username or not password:
            return self.send_json({"error": "Pseudo et mot de passe requis."}, 400)

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, is_admin FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        user = cursor.fetchone()
        conn.close()

        if not user or user["password_hash"] != password_hash:
            return self.send_json({"error": "Pseudo ou mot de passe incorrect."}, 401)

        token = base64.b64encode(f"{user['username']}:{password_hash}".encode()).decode()

        self.send_json({
            "success": True,
            "token": token,
            "user": {"id": user["id"], "username": user["username"], "is_admin": bool(user["is_admin"])},
            "message": f"Content de te revoir, {user['username']} !"
        })

    def handle_auth_me(self):
        user = self.get_current_user()
        if not user:
            return self.send_json({"error": "Non connecté."}, 401)
        self.send_json({"user": user})

    # ----------------- History & Movie Admin Handlers -----------------

    def handle_admin_move_to_history(self, movie_id):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Corps JSON invalide."}, 400)

        screening_date = str(data.get("screening_date", "")).strip()
        if not screening_date:
            return self.send_json({"error": "La date de projection est requise."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        # Check movie exists
        cursor.execute("SELECT id, title FROM movies WHERE id = ?", (movie_id,))
        movie = cursor.fetchone()
        if not movie:
            conn.close()
            return self.send_json({"error": "Film introuvable."}, 404)

        # Check not already in screenings
        cursor.execute("SELECT id FROM screenings WHERE movie_id = ?", (movie_id,))
        if cursor.fetchone():
            conn.close()
            return self.send_json({"error": "Ce film est déjà dans l'historique."}, 409)

        # Insert screening
        cursor.execute("INSERT INTO screenings (movie_id, screening_date) VALUES (?, ?)", (movie_id, screening_date))
        
        # Increment screened_count
        cursor.execute("UPDATE movies SET screened_count = screened_count + 1 WHERE id = ?", (movie_id,))
        
        conn.commit()
        conn.close()

        self.send_json({
            "success": True,
            "message": f"« {movie['title']} » ajouté à l'historique des projections !"
        }, 201)

    def handle_get_history(self):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.id as screening_id, s.screening_date, s.movie_id,
                   m.title, m.year, m.genre, m.poster_url, m.synopsis, m.runtime
            FROM screenings s
            JOIN movies m ON s.movie_id = m.id
            ORDER BY s.created_at DESC
        """)
        screenings = [dict(row) for row in cursor.fetchall()]

        # For each screening, get avg rating, review count, and word cloud
        for sc in screenings:
            mid = sc["movie_id"]

            # Reviews stats
            cursor.execute("""
                SELECT COUNT(*) as count, COALESCE(AVG(rating), 0) as avg_rating
                FROM reviews WHERE movie_id = ?
            """, (mid,))
            rev = cursor.fetchone()
            sc["review_count"] = rev["count"]
            sc["avg_rating"] = round(rev["avg_rating"], 1)

            # Word cloud
            cursor.execute("""
                SELECT LOWER(TRIM(word)) as clean_word, MAX(word) as display_word, COUNT(*) as count
                FROM word_cloud WHERE movie_id = ?
                GROUP BY clean_word ORDER BY count DESC LIMIT 15
            """, (mid,))
            sc["words"] = [{"word": r["display_word"], "count": r["count"]} for r in cursor.fetchall()]

        conn.close()
        self.send_json({"screenings": screenings})

    # ----------------- Product Management Handlers -----------------

    def handle_admin_add_product(self):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Corps JSON invalide."}, 400)

        name = str(data.get("name", "")).strip()
        price = data.get("price")
        if not name or price is None:
            return self.send_json({"error": "Nom et prix requis."}, 400)

        try:
            price = float(price)
        except (ValueError, TypeError):
            return self.send_json({"error": "Prix invalide."}, 400)

        category = str(data.get("category", "popcorn"))
        flavor = str(data.get("flavor", ""))
        size = str(data.get("size", ""))
        description = str(data.get("description", ""))
        emoji = str(data.get("emoji", "🍿"))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (name, category, flavor, size, price, description, emoji, is_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (name, category, flavor, size, price, description, emoji))
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()

        self.send_json({"success": True, "product_id": product_id, "message": f"Produit '{name}' ajouté !"}, 201)

    def handle_admin_update_product(self, product_id):
        data = self.parse_json_body()
        if not data:
            return self.send_json({"error": "Corps JSON invalide."}, 400)

        conn = get_db()
        cursor = conn.cursor()

        updates = []
        params = []

        for field in ["name", "price", "size", "flavor", "description", "emoji", "category"]:
            if field in data:
                updates.append(f"{field} = ?")
                params.append(data[field])
        if "is_available" in data:
            updates.append("is_available = ?")
            params.append(1 if data["is_available"] else 0)

        if not updates:
            conn.close()
            return self.send_json({"error": "Aucun champ à modifier."}, 400)

        params.append(product_id)
        cursor.execute(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        conn.close()

        if not product:
            return self.send_json({"error": "Produit introuvable."}, 404)

        self.send_json({"success": True, "product": dict(product), "message": "Produit mis à jour !"})

    def handle_admin_delete_product(self, product_id):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        self.send_json({"success": True, "message": "Produit supprimé."})

    # ----------------- Leaderboard / Stats Handlers -----------------

    def handle_get_leaderboard(self):
        conn = get_db()
        cursor = conn.cursor()

        # Top popcorn buyers (by total spent)
        cursor.execute("""
            SELECT LOWER(customer_name) as name, MAX(customer_name) as display_name,
                   SUM(total_price) as total_spent, COUNT(id) as order_count
            FROM orders
            GROUP BY LOWER(customer_name)
            ORDER BY total_spent DESC
            LIMIT 10
        """)
        top_buyers = [dict(row) for row in cursor.fetchall()]

        # Top cinephiles (by number of movies reviewed)
        cursor.execute("""
            SELECT LOWER(reviewer_name) as name, MAX(reviewer_name) as display_name,
                   COUNT(DISTINCT movie_id) as movies_reviewed,
                   ROUND(AVG(rating), 1) as avg_rating
            FROM reviews
            GROUP BY LOWER(reviewer_name)
            ORDER BY movies_reviewed DESC, avg_rating DESC
            LIMIT 10
        """)
        top_cinephiles = [dict(row) for row in cursor.fetchall()]

        # Rating distribution (for all users who have reviewed)
        cursor.execute("""
            SELECT LOWER(reviewer_name) as name, MAX(reviewer_name) as display_name,
                   rating, COUNT(*) as count
            FROM reviews
            GROUP BY LOWER(reviewer_name), CAST(rating AS INTEGER)
            ORDER BY name, rating
        """)
        raw_dist = cursor.fetchall()

        # Group by user
        user_distributions = {}
        for row in raw_dist:
            name = row["name"]
            if name not in user_distributions:
                user_distributions[name] = {"display_name": row["display_name"], "ratings": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}}
            star = min(5, max(1, int(row["rating"])))
            user_distributions[name]["ratings"][star] += row["count"]

        rating_distributions = [
            {"name": v["display_name"], "ratings": v["ratings"]}
            for k, v in user_distributions.items()
        ]

        # Top rated movies (screened only)
        cursor.execute("""
            SELECT m.title, m.poster_url, m.year,
                   ROUND(AVG(r.rating), 1) as avg_rating,
                   COUNT(r.id) as review_count
            FROM reviews r
            JOIN movies m ON r.movie_id = m.id
            GROUP BY m.id
            HAVING review_count >= 1
            ORDER BY avg_rating DESC, review_count DESC
            LIMIT 10
        """)
        top_rated = [dict(row) for row in cursor.fetchall()]

        # General stats
        cursor.execute("SELECT COUNT(DISTINCT LOWER(reviewer_name)) as cnt FROM reviews")
        unique_reviewers = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(DISTINCT LOWER(customer_name)) as cnt FROM orders")
        unique_buyers = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COALESCE(SUM(total_price), 0) as total FROM orders")
        total_revenue = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as cnt FROM screenings")
        total_screenings = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE is_admin = 0")
        total_users = cursor.fetchone()["cnt"]

        conn.close()

        self.send_json({
            "top_buyers": top_buyers,
            "top_cinephiles": top_cinephiles,
            "rating_distributions": rating_distributions,
            "top_rated_movies": top_rated,
            "general": {
                "unique_reviewers": unique_reviewers,
                "unique_buyers": unique_buyers,
                "total_revenue": round(total_revenue, 2),
                "total_screenings": total_screenings,
                "total_users": total_users
            }
        })

    # ----------------- Static Asset Serving -----------------

    def serve_static(self, path):
        """Sert les fichiers statiques du dossier public/ (HTML, CSS, JS, images)."""
        if path == "/" or not path:
            filename = "index.html"
        else:
            filename = path.split("?")[0].lstrip("/")

        # Nettoyage et sécurité contre le Directory Traversal
        filename = os.path.normpath(filename)
        if filename.startswith(".."):
            self.send_response(403)
            self.end_headers()
            return

        filepath = os.path.join(BASE_DIR, filename)

        if not os.path.exists(filepath) or os.path.isdir(filepath):
            self.send_response(404)
            self.end_headers()
            return

        mime_type, _ = mimetypes.guess_type(filepath)
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(filepath, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            print(f"Erreur lors de la lecture de {filepath} : {e}")
            self.send_response(500)
            self.end_headers()

def run_server(port=PORT):
    init_db()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), CinemaRequestHandler) as httpd:
        print(f"🎬 Student Cinema Server running at http://localhost:{port}")
        print(f"🔑 Admin PIN is set to '{ADMIN_PIN}'")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

# ==============================================================================
# FONCTIONS GLOBALES (0 espace d'indentation, tout à gauche)
# ==============================================================================
#getting movie info from themoviedb.org

TMDB_API_KEY = "36714c952f9cd9e486626a91fd3d16fe"

def fetch_movie_from_tmdb(title):
    if not TMDB_API_KEY or TMDB_API_KEY == "TA_CLE_API_TMDB_ICI":
        return None

    try:
        query = urllib.parse.quote(title)
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=fr-FR"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            results = data.get("results", [])
            
            if results:
                movie = results[0]
                poster_path = movie.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                synopsis = movie.get("overview") or "Aucun synopsis disponible."
                
                release_date = movie.get("release_date", "")
                year = int(release_date.split("-")[0]) if release_date and len(release_date) >= 4 else None
                
                return {
                    "title": movie.get("title") or title,
                    "poster_url": poster_url,
                    "synopsis": synopsis,
                    "year": year,
                    "genre": "Films cultes",
                    "runtime": "2h 00m"
                }
    except Exception as e:
        print(f"Erreur TMDB pour '{title}' : {e}")
    
    return None


if __name__ == "__main__":
    import sys
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)