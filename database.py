import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cinema.db")

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
        status TEXT DEFAULT 'pending', -- 'pending', 'preparing', 'ready', 'collected'
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

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

    conn.commit()
    conn.close()

def get_kinepolics_products():
    return [
        ("Petit sucré", "", "Sucré", "Petit", 1.00, "", "🍿", 1),
        ("Petit salé", "", "Salé", "Petit", 1.00, "", "🍿", 1),
        ("Moyen sucré", "", "Sucré", "Moyen", 1.50, "", "🍿", 1),
        ("Moyen salé", "", "Salé", "Moyen", 1.50, "", "🍿", 1),
        ("Grand sucré", "", "Sucré", "Grand", 2, "", "🍿", 1),
        ("Grand salé", "", "Salé", "Grand", 2, "", "🍿", 1),
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
        ("Sans un bruit (A Quiet Place)", 2018, "Horreur", "1h 30m", "Une famille doit vivre dans le silence le plus absolu pour échapper à des créatures aveugles.", "https://images.unsplash.com/photo-1509281373149-e957c6296406?w=600", 0),
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

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)


