"""
Banques de données synthétiques pour construire le dataset.

Chaque projet / expérience possède :
- des descriptions BRUTES (comme un utilisateur ou l'extracteur les écrirait) ;
- des PUCES reformulées, fidèles : aucune information absente du texte brut.
"""

FIRST_NAMES = [
    "Amine", "Sara", "Youssef", "Nour", "Mohamed", "Yasmine", "Ahmed", "Ines",
    "Omar", "Mariem", "Khalil", "Rania", "Aziz", "Eya", "Hamza", "Salma",
    "Mehdi", "Asma", "Wassim", "Oumaima", "Firas", "Chaima", "Skander", "Lina",
    "Bilel", "Rim", "Anis", "Hiba", "Walid", "Molka", "Karim", "Emna",
    "Lucas", "Camille", "Thomas", "Léa", "Hugo", "Manon", "Nicolas", "Chloé",
    "Malek", "Fady", "Brahim", "Ghada", "Seif", "Dorra", "Achraf", "Imen",
]

LAST_NAMES = [
    "Ben Salem", "Trabelsi", "Gharbi", "Ben Amor", "Jlassi", "Mansouri", "Hammami",
    "Bouazizi", "Chebbi", "Dridi", "Ayari", "Khelifi", "Sassi", "Mejri", "Baccouche",
    "Ben Ali", "Ferchichi", "Zouari", "Karray", "Masmoudi", "Bejaoui", "Garram",
    "Laabidi", "Ouni", "Riahi", "Toumi", "Haddad", "Jaziri", "Kammoun", "Fourati",
    "Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Lefebvre", "Girard", "Roux",
]

EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.fr", "esprit.tn", "example.com", "hotmail.com"]

CITIES_TN = ["Tunis", "Ariana", "Sousse", "Sfax", "Monastir", "Nabeul", "Bizerte",
             "La Marsa", "Ben Arous", "Gabès", "Kairouan", "Tunis, Tunisie", "Sousse, Tunisie"]
CITIES_FR = ["Paris", "Lyon", "Lille", "Toulouse", "Montpellier", "Paris, France", "Nantes"]

INSTITUTIONS = [
    ("ESPRIT", "Ariana"), ("INSAT", "Tunis"), ("ENIT", "Tunis"), ("ENSI", "Manouba"),
    ("Institut Supérieur d'Informatique", "Ariana"), ("FST", "Tunis"),
    ("ISET Radès", "Radès"), ("ISIMS", "Sfax"), ("ENIS", "Sfax"), ("ISITCom", "Hammam Sousse"),
    ("Faculté des Sciences de Monastir", "Monastir"), ("SUP'COM", "Ariana"),
    ("Université Paris-Saclay", "Paris"), ("IHEC Carthage", "Carthage"),
    ("ISG Tunis", "Tunis"), ("Polytech Lille", "Lille"), ("ENSIT", "Tunis"),
    ("Université Centrale", "Tunis"), ("ISSAT Sousse", "Sousse"), ("TEK-UP", "Ariana"),
]

LYCEES = ["Lycée Pilote de Sousse", "Lycée Pilote de Tunis", "Lycée Bourguiba",
          "Lycée Ibn Khaldoun", "Lycée Pilote de Sfax", "Lycée Carnot"]
BAC_FIELDS = ["Mathématiques", "Sciences informatiques", "Sciences expérimentales", "Techniques"]

MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
          "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

LANGUAGES = {
    "Arabe": ["Langue maternelle", "Natif", None],
    "Français": ["Courant", "Bilingue", "B2", "C1", "Professionnel", None],
    "Anglais": ["B1", "B2", "C1", "Intermédiaire", "Courant", "Professionnel", None],
    "Allemand": ["A2", "Notions", "B1", None],
    "Espagnol": ["Notions", "A2", None],
    "Italien": ["Notions", "A1", None],
}

INTERESTS = [
    "Football", "Lecture", "Photographie", "Échecs", "Bénévolat associatif",
    "Hackathons", "Randonnée", "Musique", "Voyages", "Jeux vidéo", "Natation",
    "Club robotique", "Veille technologique", "Cinéma", "Cuisine", "Basketball",
    "Dessin", "Théâtre", "Course à pied", "Club IEEE",
]

CERTIFICATIONS = [
    ("AWS Certified Cloud Practitioner", "Amazon Web Services"),
    ("Oracle Certified Associate Java SE 8", "Oracle"),
    ("Scrum Foundation Professional Certificate", "CertiProf"),
    ("Google Data Analytics", "Coursera"),
    ("CCNA", "Cisco"),
    ("Microsoft Azure Fundamentals (AZ-900)", "Microsoft"),
    ("Docker Foundations", "Docker"),
    ("Meta Front-End Developer", "Coursera"),
    ("PSM I", "Scrum.org"),
    ("TOEIC", "ETS"),
    ("DELF B2", "France Éducation International"),
    ("Machine Learning Specialization", "Coursera"),
    ("Certified Kubernetes Application Developer", "CNCF"),
    ("Power BI Data Analyst (PL-300)", "Microsoft"),
    ("Python for Everybody", "Coursera"),
    ("Linux Essentials", "LPI"),
]

COMPANIES = [
    ("Vermeg", "Tunis"), ("Sofrecom", "Tunis"), ("Talan", "Tunis"), ("Telnet", "Ariana"),
    ("Orange Tunisie", "Tunis"), ("Ooredoo", "Tunis"), ("Capgemini", "Paris"),
    ("Sopra HR Software", "Tunis"), ("Proxym Group", "Sousse"), ("Expensya", "Tunis"),
    ("InstaDeep", "Tunis"), ("BIAT", "Tunis"), ("Linedata", "Tunis"), ("Focus Corporation", "Ariana"),
    ("Value Digital Services", "Tunis"), ("Wevioo", "Tunis"), ("Actia Engineering Services", "Ariana"),
    ("Draexlmaier", "Sousse"), ("Leoni", "Sousse"), ("Satoripop", "Tunis"),
    ("Smart Solutions R&D", "Sfax"), ("Dataviz Studio", "Lyon"), ("Atos", "Lyon"),
    ("STMicroelectronics", "Tunis"), ("Tunisie Telecom", "Tunis"), ("Keyrus", "Tunis"),
    ("Freelance", None), ("Startup Wiki", "Sousse"), ("Cynapsys", "Tunis"),
]

# ----------------------------------------------------------------------
# Domaines (tracks)
# ----------------------------------------------------------------------

TRACKS = {}

TRACKS["java"] = {
    "fields": ["Génie logiciel", "Informatique", "Ingénierie des systèmes d'information"],
    "titles": ["Développeur Full-Stack Java / Angular", "Ingénieur logiciel Java",
               "Développeur back-end Spring Boot", "Stage de fin d'études en développement Java"],
    "skills": {
        "Langages": ["Java", "TypeScript", "JavaScript", "SQL", "Python", "C"],
        "Frameworks": ["Spring Boot", "Angular", "Hibernate", "Spring Security", "JUnit"],
        "Bases de données": ["MySQL", "PostgreSQL", "Oracle", "MongoDB"],
        "Outils": ["Git", "Maven", "Docker", "Postman", "Jira", "IntelliJ IDEA", "SonarQube"],
        "Méthodologies": ["Scrum", "UML", "Architecture microservices", "API REST"],
    },
    "projects": [
        {
            "name": "Application de gestion de stock",
            "technologies": ["Spring Boot", "Angular", "MySQL"],
            "raw": [
                "j'ai développé une appli web de gestion de stock avec spring boot et angular, avec une base mysql. elle gère les produits, les fournisseurs et les alertes de rupture",
                "Application web de gestion de stock (produits, fournisseurs, alertes de rupture) avec Spring Boot, Angular et MySQL.",
            ],
            "bullets": [
                "Développement d'une application web de gestion de stock avec Spring Boot et Angular",
                "Gestion des produits, des fournisseurs et des alertes de rupture",
                "Stockage des données dans une base MySQL",
            ],
        },
        {
            "name": "Plateforme de réservation de salles",
            "technologies": ["Spring Boot", "Angular", "PostgreSQL", "JWT"],
            "raw": [
                "plateforme de réservation de salles de réunion. back en spring boot, front angular, base postgresql, authentification jwt",
                "J'ai réalisé une plateforme pour réserver des salles de réunion. Le back-end est en Spring Boot, le front en Angular, avec PostgreSQL et une authentification JWT.",
            ],
            "bullets": [
                "Réalisation d'une plateforme de réservation de salles de réunion",
                "Développement du back-end avec Spring Boot et du front-end avec Angular",
                "Mise en place d'une authentification JWT et d'une base PostgreSQL",
            ],
        },
        {
            "name": "Application de gestion de projets freelance",
            "technologies": ["Angular", "Spring Boot"],
            "raw": [
                "J'ai réalisé une application de gestion de projets freelance avec Angular et Spring Boot.",
                "appli de gestion de projets pour freelances en angular + spring boot",
            ],
            "bullets": [
                "Développement d'une application de gestion de projets freelance avec Angular et Spring Boot",
            ],
        },
        {
            "name": "E-banking",
            "technologies": ["Spring Boot", "Angular", "Spring Security", "MySQL"],
            "raw": [
                "application e-banking : consultation des comptes, virements et historique des opérations. sécurisée avec spring security. spring boot / angular / mysql",
                "Application de banque en ligne permettant la consultation des comptes, les virements et l'historique des opérations, sécurisée avec Spring Security.",
            ],
            "bullets": [
                "Conception d'une application de banque en ligne : consultation des comptes, virements et historique des opérations",
                "Sécurisation de l'application avec Spring Security",
            ],
        },
        {
            "name": "Microservices de gestion des commandes",
            "technologies": ["Spring Cloud", "Docker", "Kafka"],
            "raw": [
                "architecture microservices pour gérer des commandes avec spring cloud, communication via kafka et déploiement avec docker",
                "J'ai conçu une architecture microservices de gestion des commandes : Spring Cloud, échanges via Kafka, conteneurs Docker.",
            ],
            "bullets": [
                "Conception d'une architecture microservices de gestion des commandes avec Spring Cloud",
                "Communication entre services via Kafka",
                "Déploiement des services avec Docker",
            ],
        },
        {
            "name": "Gestion d'une clinique",
            "technologies": ["Java", "JavaFX", "MySQL"],
            "raw": [
                "application desktop en javafx pour gérer les patients et les rendez-vous d'une clinique, base mysql",
                "Application de bureau JavaFX de gestion des patients et des rendez-vous d'une clinique avec une base MySQL.",
            ],
            "bullets": [
                "Développement d'une application de bureau JavaFX de gestion des patients et des rendez-vous",
                "Persistance des données avec MySQL",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire développeur Java",
            "raw": [
                "j'ai développé des API REST avec spring boot et écrit des tests unitaires avec junit",
                "Développement d'API REST en Spring Boot et écriture de tests unitaires JUnit.",
            ],
            "bullets": [
                "Développement d'API REST avec Spring Boot",
                "Écriture de tests unitaires avec JUnit",
            ],
        },
        {
            "role": "Développeur Full-Stack",
            "raw": [
                "je travaille sur une application RH : nouvelles fonctionnalités en angular et spring boot, correction de bugs et participation aux sprints scrum",
                "Développement de nouvelles fonctionnalités d'une application RH en Angular et Spring Boot, correction de bugs, participation aux sprints Scrum.",
            ],
            "bullets": [
                "Développement de nouvelles fonctionnalités d'une application RH avec Angular et Spring Boot",
                "Correction de bugs",
                "Participation aux sprints Scrum",
            ],
        },
        {
            "role": "Stage de fin d'études",
            "raw": [
                "pendant mon PFE j'ai migré un module de facturation d'une application monolithique vers des microservices spring boot",
                "Migration d'un module de facturation d'une application monolithique vers des microservices Spring Boot.",
            ],
            "bullets": [
                "Migration d'un module de facturation d'une application monolithique vers des microservices Spring Boot",
            ],
        },
        {
            "role": "Stagiaire en développement web",
            "raw": [
                "j'ai créé un tableau de bord angular pour suivre les réclamations clients et je l'ai connecté à une API spring boot existante",
                "Création d'un tableau de bord Angular de suivi des réclamations clients, connecté à une API Spring Boot existante.",
            ],
            "bullets": [
                "Création d'un tableau de bord Angular de suivi des réclamations clients",
                "Intégration avec une API Spring Boot existante",
            ],
        },
    ],
}

TRACKS["js"] = {
    "fields": ["Informatique", "Technologies de l'information", "Développement web et multimédia"],
    "titles": ["Développeur front-end React", "Développeur MERN", "Développeur web Full-Stack JavaScript",
               "Développeuse web"],
    "skills": {
        "Langages": ["JavaScript", "TypeScript", "HTML", "CSS", "PHP", "SQL"],
        "Front-end": ["React", "Next.js", "Vue.js", "Tailwind CSS", "Bootstrap", "Redux"],
        "Back-end": ["Node.js", "Express", "NestJS", "Laravel", "Symfony"],
        "Bases de données": ["MongoDB", "MySQL", "PostgreSQL", "Firebase"],
        "Outils": ["Git", "GitHub", "Figma", "Docker", "Postman", "Vercel"],
    },
    "projects": [
        {
            "name": "Site e-commerce",
            "technologies": ["React", "Node.js", "Express", "MongoDB"],
            "raw": [
                "j'ai fait un site e-commerce avec react et node express, base mongodb. il y a un panier, le paiement en ligne et un espace admin",
                "Site e-commerce (panier, paiement en ligne, espace administrateur) développé avec React, Node.js/Express et MongoDB.",
            ],
            "bullets": [
                "Développement d'un site e-commerce avec React, Node.js, Express et MongoDB",
                "Mise en place du panier, du paiement en ligne et d'un espace administrateur",
            ],
        },
        {
            "name": "Portfolio personnel",
            "technologies": ["Next.js", "Tailwind CSS"],
            "raw": [
                "portfolio perso en next.js et tailwind, déployé sur vercel",
                "J'ai créé mon portfolio personnel avec Next.js et Tailwind CSS et je l'ai déployé sur Vercel.",
            ],
            "bullets": [
                "Création d'un portfolio personnel avec Next.js et Tailwind CSS",
                "Déploiement sur Vercel",
            ],
        },
        {
            "name": "Application de chat en temps réel",
            "technologies": ["Socket.io", "React", "Node.js"],
            "raw": [
                "appli de chat en temps réel avec socket.io, react et node. salons de discussion et notifications",
                "Application de messagerie en temps réel avec salons de discussion et notifications (Socket.io, React, Node.js).",
            ],
            "bullets": [
                "Développement d'une application de messagerie en temps réel avec Socket.io, React et Node.js",
                "Gestion des salons de discussion et des notifications",
            ],
        },
        {
            "name": "Blog collaboratif",
            "technologies": ["Laravel", "MySQL", "Bootstrap"],
            "raw": [
                "blog collaboratif en laravel avec mysql et bootstrap : articles, commentaires et gestion des rôles",
                "J'ai développé un blog collaboratif sous Laravel : articles, commentaires et rôles utilisateurs, avec MySQL et Bootstrap.",
            ],
            "bullets": [
                "Développement d'un blog collaboratif avec Laravel, MySQL et Bootstrap",
                "Gestion des articles, des commentaires et des rôles utilisateurs",
            ],
        },
        {
            "name": "Gestionnaire de tâches",
            "technologies": ["Vue.js", "Firebase"],
            "raw": [
                "petite appli de to-do list en vue.js avec firebase pour l'authentification et le stockage",
                "Application de gestion de tâches en Vue.js utilisant Firebase pour l'authentification et le stockage.",
            ],
            "bullets": [
                "Réalisation d'une application de gestion de tâches avec Vue.js",
                "Utilisation de Firebase pour l'authentification et le stockage des données",
            ],
        },
        {
            "name": "Plateforme de covoiturage",
            "technologies": ["NestJS", "React", "PostgreSQL"],
            "raw": [
                "plateforme de covoiturage : publication de trajets, réservation de places et notation des conducteurs. nestjs, react, postgresql",
                "Plateforme de covoiturage permettant de publier des trajets, réserver des places et noter les conducteurs, développée avec NestJS, React et PostgreSQL.",
            ],
            "bullets": [
                "Conception d'une plateforme de covoiturage avec NestJS, React et PostgreSQL",
                "Publication de trajets, réservation de places et notation des conducteurs",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire développeur front-end",
            "raw": [
                "j'ai intégré des maquettes figma en react et amélioré le responsive du site",
                "Intégration de maquettes Figma en React et amélioration du responsive design.",
            ],
            "bullets": [
                "Intégration de maquettes Figma avec React",
                "Amélioration de l'affichage responsive du site",
            ],
        },
        {
            "role": "Développeur web",
            "raw": [
                "je développe et maintiens des sites vitrines wordpress et des applications laravel pour des clients",
                "Développement et maintenance de sites vitrines WordPress et d'applications Laravel pour des clients.",
            ],
            "bullets": [
                "Développement et maintenance de sites vitrines WordPress",
                "Réalisation d'applications Laravel pour des clients",
            ],
        },
        {
            "role": "Développeur Full-Stack JavaScript",
            "raw": [
                "développement d'une API node.js/express et d'un back-office react, avec revue de code sur github",
                "J'ai développé une API Node.js/Express et un back-office React, et participé aux revues de code sur GitHub.",
            ],
            "bullets": [
                "Développement d'une API avec Node.js et Express",
                "Réalisation d'un back-office avec React",
                "Participation aux revues de code sur GitHub",
            ],
        },
        {
            "role": "Stagiaire en développement web",
            "raw": [
                "refonte de la page d'accueil du site de l'entreprise et optimisation du temps de chargement",
                "J'ai refait la page d'accueil du site de l'entreprise et optimisé le temps de chargement.",
            ],
            "bullets": [
                "Refonte de la page d'accueil du site de l'entreprise",
                "Optimisation du temps de chargement",
            ],
        },
    ],
}

TRACKS["python_web"] = {
    "fields": ["Informatique", "Génie logiciel", "Informatique appliquée"],
    "titles": ["Développeur Python / Django", "Développeur back-end Python", "Ingénieur logiciel"],
    "skills": {
        "Langages": ["Python", "JavaScript", "SQL", "Bash", "C"],
        "Frameworks": ["Django", "FastAPI", "Flask", "Django REST Framework", "Celery"],
        "Bases de données": ["PostgreSQL", "SQLite", "Redis", "MongoDB"],
        "Outils": ["Git", "Docker", "Linux", "Pytest", "GitLab CI", "Nginx"],
    },
    "projects": [
        {
            "name": "API de gestion de bibliothèque",
            "technologies": ["FastAPI", "PostgreSQL", "Docker"],
            "raw": [
                "api rest en fastapi pour gérer les livres et les emprunts d'une bibliothèque, base postgresql, conteneurisée avec docker",
                "API REST FastAPI de gestion des livres et des emprunts, avec PostgreSQL et Docker.",
            ],
            "bullets": [
                "Développement d'une API REST de gestion des livres et des emprunts avec FastAPI",
                "Stockage des données dans PostgreSQL et conteneurisation avec Docker",
            ],
        },
        {
            "name": "Site d'annonces immobilières",
            "technologies": ["Django", "PostgreSQL", "Bootstrap"],
            "raw": [
                "site d'annonces immobilières en django : recherche par ville et par prix, espace propriétaire",
                "J'ai développé un site d'annonces immobilières avec Django (recherche par ville et par prix, espace propriétaire).",
            ],
            "bullets": [
                "Développement d'un site d'annonces immobilières avec Django",
                "Recherche par ville et par prix, espace dédié aux propriétaires",
            ],
        },
        {
            "name": "Bot Telegram de rappels",
            "technologies": ["Python", "Telegram API", "SQLite"],
            "raw": [
                "bot telegram en python qui envoie des rappels programmés, les rappels sont stockés dans sqlite",
                "Bot Telegram en Python envoyant des rappels programmés stockés dans une base SQLite.",
            ],
            "bullets": [
                "Création d'un bot Telegram en Python envoyant des rappels programmés",
                "Stockage des rappels dans une base SQLite",
            ],
        },
        {
            "name": "Scraper de prix",
            "technologies": ["Python", "BeautifulSoup", "Pandas"],
            "raw": [
                "script de scraping qui récupère les prix de produits sur plusieurs sites et les compare avec pandas",
                "J'ai écrit un scraper Python (BeautifulSoup) qui récupère les prix de produits sur plusieurs sites, puis une comparaison avec Pandas.",
            ],
            "bullets": [
                "Développement d'un scraper récupérant les prix de produits sur plusieurs sites",
                "Comparaison des prix avec Pandas",
            ],
        },
        {
            "name": "Application de gestion des absences",
            "technologies": ["Flask", "MySQL"],
            "raw": [
                "appli flask pour que les enseignants saisissent les absences des étudiants, avec export pdf",
                "Application Flask permettant aux enseignants de saisir les absences des étudiants, avec export PDF et base MySQL.",
            ],
            "bullets": [
                "Développement d'une application Flask de saisie des absences des étudiants",
                "Export des données au format PDF",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire développeur Python",
            "raw": [
                "j'ai automatisé la génération de rapports excel avec python et créé des tâches planifiées avec celery",
                "Automatisation de la génération de rapports Excel en Python et création de tâches planifiées avec Celery.",
            ],
            "bullets": [
                "Automatisation de la génération de rapports Excel avec Python",
                "Création de tâches planifiées avec Celery",
            ],
        },
        {
            "role": "Développeur back-end",
            "raw": [
                "développement de services django rest framework, écriture de tests pytest et mise en place d'une pipeline gitlab ci",
                "Je développe des services Django REST Framework, j'écris des tests Pytest et j'ai mis en place une pipeline GitLab CI.",
            ],
            "bullets": [
                "Développement de services avec Django REST Framework",
                "Écriture de tests avec Pytest",
                "Mise en place d'une pipeline d'intégration continue GitLab CI",
            ],
        },
        {
            "role": "Stage d'été",
            "raw": [
                "j'ai développé un module d'authentification pour une application django existante",
                "Développement d'un module d'authentification pour une application Django existante.",
            ],
            "bullets": [
                "Développement d'un module d'authentification pour une application Django existante",
            ],
        },
    ],
}

TRACKS["data"] = {
    "fields": ["Data science", "Intelligence artificielle", "Science des données", "Informatique"],
    "titles": ["Data Scientist junior", "Ingénieur en intelligence artificielle", "Data Analyst",
               "Ingénieur machine learning"],
    "skills": {
        "Langages": ["Python", "R", "SQL"],
        "Data & IA": ["Pandas", "NumPy", "scikit-learn", "TensorFlow", "PyTorch", "Keras",
                      "LangChain", "Hugging Face", "OpenCV", "NLTK"],
        "Visualisation": ["Matplotlib", "Seaborn", "Power BI", "Tableau", "Plotly"],
        "Outils": ["Jupyter", "Git", "Docker", "MLflow", "Google Colab", "Streamlit"],
        "Bases de données": ["PostgreSQL", "MongoDB", "MySQL"],
    },
    "projects": [
        {
            "name": "Prédiction des prix immobiliers",
            "technologies": ["Python", "scikit-learn"],
            "raw": [
                "projet universitaire de prédiction des prix immobiliers avec scikit-learn",
                "Projet universitaire : prédiction des prix immobiliers à l'aide de scikit-learn.",
            ],
            "bullets": [
                "Prédiction des prix immobiliers à l'aide de modèles scikit-learn (projet universitaire)",
            ],
        },
        {
            "name": "Détection de fraude bancaire",
            "technologies": ["Python", "XGBoost", "Pandas"],
            "raw": [
                "modèle de détection de fraude sur des transactions bancaires avec xgboost. j'ai traité le déséquilibre des classes avec SMOTE",
                "Détection de fraude sur des transactions bancaires avec XGBoost et traitement du déséquilibre des classes avec SMOTE.",
            ],
            "bullets": [
                "Développement d'un modèle de détection de fraude sur des transactions bancaires avec XGBoost",
                "Traitement du déséquilibre des classes avec SMOTE",
            ],
        },
        {
            "name": "Chatbot RAG",
            "technologies": ["LangChain", "FAISS", "Streamlit"],
            "raw": [
                "chatbot qui répond aux questions sur des documents pdf avec langchain et un index faiss, interface streamlit",
                "J'ai développé un chatbot RAG répondant à des questions sur des documents PDF (LangChain, FAISS) avec une interface Streamlit.",
            ],
            "bullets": [
                "Développement d'un chatbot RAG répondant à des questions sur des documents PDF",
                "Indexation des documents avec FAISS et orchestration avec LangChain",
                "Création d'une interface utilisateur avec Streamlit",
            ],
        },
        {
            "name": "Classification d'images médicales",
            "technologies": ["TensorFlow", "Keras"],
            "raw": [
                "cnn pour classifier des radiographies pulmonaires avec tensorflow/keras, avec data augmentation",
                "Classification de radiographies pulmonaires avec un CNN (TensorFlow, Keras) et augmentation de données.",
            ],
            "bullets": [
                "Classification de radiographies pulmonaires avec un réseau de neurones convolutif",
                "Utilisation de TensorFlow, Keras et de techniques d'augmentation de données",
            ],
        },
        {
            "name": "Analyse des ventes",
            "technologies": ["Power BI", "SQL"],
            "raw": [
                "tableau de bord power bi pour analyser les ventes par région et par produit à partir d'une base sql",
                "Tableau de bord Power BI d'analyse des ventes par région et par produit, alimenté par une base SQL.",
            ],
            "bullets": [
                "Conception d'un tableau de bord Power BI d'analyse des ventes par région et par produit",
                "Extraction des données depuis une base SQL",
            ],
        },
        {
            "name": "Analyse de sentiments",
            "technologies": ["Python", "Hugging Face", "NLTK"],
            "raw": [
                "analyse de sentiments sur des avis clients en arabe et en français avec un modèle hugging face, prétraitement avec nltk",
                "J'ai réalisé une analyse de sentiments d'avis clients en arabe et en français (modèle Hugging Face, prétraitement NLTK).",
            ],
            "bullets": [
                "Analyse de sentiments d'avis clients en arabe et en français avec un modèle Hugging Face",
                "Prétraitement des textes avec NLTK",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire Data Scientist",
            "raw": [
                "j'ai nettoyé et analysé des données clients avec pandas puis entraîné un modèle de prédiction du churn",
                "Nettoyage et analyse de données clients avec Pandas, entraînement d'un modèle de prédiction du churn.",
            ],
            "bullets": [
                "Nettoyage et analyse de données clients avec Pandas",
                "Entraînement d'un modèle de prédiction du churn",
            ],
        },
        {
            "role": "Data Analyst",
            "raw": [
                "création de rapports power bi pour la direction commerciale et automatisation des extractions sql",
                "Je crée des rapports Power BI pour la direction commerciale et j'ai automatisé les extractions SQL.",
            ],
            "bullets": [
                "Création de rapports Power BI pour la direction commerciale",
                "Automatisation des extractions de données SQL",
            ],
        },
        {
            "role": "Stage de fin d'études en IA",
            "raw": [
                "pfe : fine-tuning d'un modèle de langage pour classer des tickets de support, suivi des expériences avec mlflow",
                "Fine-tuning d'un modèle de langage pour la classification de tickets de support, suivi des expériences avec MLflow.",
            ],
            "bullets": [
                "Fine-tuning d'un modèle de langage pour la classification de tickets de support",
                "Suivi des expériences avec MLflow",
            ],
        },
        {
            "role": "Stagiaire en vision par ordinateur",
            "raw": [
                "détection de défauts sur des pièces industrielles à partir d'images avec opencv et pytorch",
                "J'ai travaillé sur la détection de défauts de pièces industrielles à partir d'images (OpenCV, PyTorch).",
            ],
            "bullets": [
                "Détection de défauts sur des pièces industrielles à partir d'images",
                "Utilisation d'OpenCV et de PyTorch",
            ],
        },
    ],
}

TRACKS["mobile"] = {
    "fields": ["Informatique", "Génie logiciel", "Développement mobile"],
    "titles": ["Développeur mobile Flutter", "Développeur Android", "Développeur mobile cross-platform"],
    "skills": {
        "Langages": ["Dart", "Kotlin", "Java", "Swift", "JavaScript"],
        "Mobile": ["Flutter", "Android SDK", "Jetpack Compose", "React Native", "SwiftUI"],
        "Back-end": ["Firebase", "Node.js", "Spring Boot"],
        "Outils": ["Git", "Android Studio", "Figma", "Postman", "Xcode"],
    },
    "projects": [
        {
            "name": "Application de livraison de repas",
            "technologies": ["Flutter", "Firebase"],
            "raw": [
                "appli mobile flutter de livraison de repas avec suivi de commande et notifications push via firebase",
                "Application mobile Flutter de livraison de repas : suivi des commandes et notifications push avec Firebase.",
            ],
            "bullets": [
                "Développement d'une application mobile de livraison de repas avec Flutter",
                "Suivi des commandes et notifications push avec Firebase",
            ],
        },
        {
            "name": "Application de suivi sportif",
            "technologies": ["Kotlin", "Jetpack Compose", "Room"],
            "raw": [
                "app android en kotlin et jetpack compose pour suivre ses séances de sport, données stockées en local avec room",
                "J'ai développé une application Android (Kotlin, Jetpack Compose) de suivi des séances de sport avec stockage local Room.",
            ],
            "bullets": [
                "Développement d'une application Android de suivi des séances de sport avec Kotlin et Jetpack Compose",
                "Stockage local des données avec Room",
            ],
        },
        {
            "name": "Application de réservation de taxis",
            "technologies": ["React Native", "Node.js", "Google Maps API"],
            "raw": [
                "application de réservation de taxis en react native avec géolocalisation google maps et un back-end node.js",
                "Application React Native de réservation de taxis avec géolocalisation (Google Maps API) et back-end Node.js.",
            ],
            "bullets": [
                "Réalisation d'une application de réservation de taxis avec React Native",
                "Intégration de la géolocalisation avec Google Maps API",
                "Développement du back-end avec Node.js",
            ],
        },
        {
            "name": "Application de quiz éducatif",
            "technologies": ["Flutter", "SQLite"],
            "raw": [
                "petit jeu de quiz éducatif pour enfants en flutter, scores enregistrés avec sqlite",
                "Quiz éducatif pour enfants développé en Flutter, avec sauvegarde des scores dans SQLite.",
            ],
            "bullets": [
                "Création d'un quiz éducatif pour enfants avec Flutter",
                "Sauvegarde des scores dans une base SQLite",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire développeur mobile",
            "raw": [
                "j'ai développé des écrans flutter et intégré des API REST dans l'application mobile de l'entreprise",
                "Développement d'écrans Flutter et intégration d'API REST dans l'application mobile de l'entreprise.",
            ],
            "bullets": [
                "Développement d'écrans de l'application mobile avec Flutter",
                "Intégration d'API REST",
            ],
        },
        {
            "role": "Développeur Android",
            "raw": [
                "maintenance d'une application android bancaire en kotlin, correction de bugs et ajout du mode sombre",
                "Je maintiens une application Android bancaire en Kotlin : correction de bugs et ajout du mode sombre.",
            ],
            "bullets": [
                "Maintenance d'une application Android bancaire en Kotlin",
                "Correction de bugs et ajout du mode sombre",
            ],
        },
        {
            "role": "Développeur mobile freelance",
            "raw": [
                "réalisation d'applications flutter pour des petits commerces et publication sur le play store",
                "J'ai réalisé des applications Flutter pour de petits commerces et je les ai publiées sur le Play Store.",
            ],
            "bullets": [
                "Réalisation d'applications Flutter pour de petits commerces",
                "Publication des applications sur le Play Store",
            ],
        },
    ],
}

TRACKS["devops"] = {
    "fields": ["Réseaux et télécommunications", "Cloud computing", "Informatique", "Génie logiciel"],
    "titles": ["Ingénieur DevOps", "Ingénieur cloud", "Administrateur systèmes et réseaux"],
    "skills": {
        "DevOps": ["Docker", "Kubernetes", "Jenkins", "GitLab CI", "Ansible", "Terraform", "Helm"],
        "Cloud": ["AWS", "Azure", "Google Cloud"],
        "Systèmes": ["Linux", "Bash", "Nginx", "Windows Server"],
        "Monitoring": ["Prometheus", "Grafana", "ELK"],
        "Langages": ["Python", "Bash", "YAML", "Go"],
    },
    "projects": [
        {
            "name": "Pipeline CI/CD",
            "technologies": ["Jenkins", "Docker", "SonarQube"],
            "raw": [
                "pipeline ci/cd avec jenkins : build, analyse sonarqube, création de l'image docker et déploiement automatique",
                "Pipeline CI/CD Jenkins comprenant le build, l'analyse SonarQube, la création d'une image Docker et le déploiement automatique.",
            ],
            "bullets": [
                "Mise en place d'une pipeline CI/CD avec Jenkins",
                "Automatisation du build, de l'analyse SonarQube, de la création d'images Docker et du déploiement",
            ],
        },
        {
            "name": "Cluster Kubernetes",
            "technologies": ["Kubernetes", "Helm", "Prometheus", "Grafana"],
            "raw": [
                "déploiement d'une application microservices sur un cluster kubernetes avec helm, supervision avec prometheus et grafana",
                "J'ai déployé une application microservices sur Kubernetes avec Helm et mis en place la supervision Prometheus/Grafana.",
            ],
            "bullets": [
                "Déploiement d'une application microservices sur un cluster Kubernetes avec Helm",
                "Supervision avec Prometheus et Grafana",
            ],
        },
        {
            "name": "Infrastructure as Code",
            "technologies": ["Terraform", "AWS", "Ansible"],
            "raw": [
                "provisionnement d'une infrastructure aws (ec2, vpc, s3) avec terraform et configuration des serveurs avec ansible",
                "Provisionnement d'une infrastructure AWS (EC2, VPC, S3) avec Terraform et configuration des serveurs avec Ansible.",
            ],
            "bullets": [
                "Provisionnement d'une infrastructure AWS (EC2, VPC, S3) avec Terraform",
                "Configuration des serveurs avec Ansible",
            ],
        },
        {
            "name": "Mise en place d'un réseau d'entreprise",
            "technologies": ["Cisco Packet Tracer", "VLAN", "OSPF"],
            "raw": [
                "simulation d'un réseau d'entreprise sur packet tracer avec des vlan et du routage ospf",
                "Conception d'un réseau d'entreprise simulé sous Cisco Packet Tracer : VLAN et routage OSPF.",
            ],
            "bullets": [
                "Conception d'un réseau d'entreprise sous Cisco Packet Tracer",
                "Configuration de VLAN et du routage OSPF",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire DevOps",
            "raw": [
                "j'ai conteneurisé des applications avec docker et écrit des pipelines gitlab ci pour les déployer",
                "Conteneurisation d'applications avec Docker et écriture de pipelines GitLab CI pour leur déploiement.",
            ],
            "bullets": [
                "Conteneurisation d'applications avec Docker",
                "Écriture de pipelines GitLab CI pour le déploiement",
            ],
        },
        {
            "role": "Ingénieur cloud",
            "raw": [
                "gestion de l'infrastructure azure de l'entreprise, automatisation avec terraform et réduction de 20% des coûts cloud",
                "Gestion de l'infrastructure Azure, automatisation avec Terraform et réduction de 20% des coûts cloud.",
            ],
            "bullets": [
                "Gestion de l'infrastructure Azure de l'entreprise",
                "Automatisation du provisionnement avec Terraform",
                "Réduction de 20% des coûts cloud",
            ],
        },
        {
            "role": "Administrateur systèmes",
            "raw": [
                "administration de serveurs linux, gestion des sauvegardes et supervision avec grafana",
                "J'administre des serveurs Linux, je gère les sauvegardes et la supervision avec Grafana.",
            ],
            "bullets": [
                "Administration de serveurs Linux",
                "Gestion des sauvegardes et supervision avec Grafana",
            ],
        },
    ],
}

TRACKS["embedded"] = {
    "fields": ["Systèmes embarqués", "Génie électrique", "Électronique", "Informatique industrielle"],
    "titles": ["Ingénieur systèmes embarqués", "Développeur C/C++ embarqué", "Ingénieur IoT"],
    "skills": {
        "Langages": ["C", "C++", "Python", "VHDL", "Assembleur"],
        "Embarqué": ["STM32", "Arduino", "Raspberry Pi", "FreeRTOS", "ESP32", "Linux embarqué"],
        "Protocoles": ["I2C", "SPI", "UART", "CAN", "MQTT"],
        "Outils": ["STM32CubeIDE", "MATLAB", "Simulink", "Git", "Proteus", "KiCad"],
    },
    "projects": [
        {
            "name": "Station météo connectée",
            "technologies": ["ESP32", "MQTT", "Node-RED"],
            "raw": [
                "station météo avec un esp32 qui mesure la température et l'humidité et envoie les données en mqtt vers node-red",
                "Station météo connectée : ESP32 mesurant la température et l'humidité, envoi des données via MQTT vers Node-RED.",
            ],
            "bullets": [
                "Réalisation d'une station météo connectée basée sur un ESP32",
                "Mesure de la température et de l'humidité et envoi des données via MQTT vers Node-RED",
            ],
        },
        {
            "name": "Robot suiveur de ligne",
            "technologies": ["Arduino", "C"],
            "raw": [
                "robot suiveur de ligne programmé en c sur arduino avec des capteurs infrarouges, pour une compétition de robotique",
                "Robot suiveur de ligne sur Arduino programmé en C avec capteurs infrarouges, réalisé pour une compétition de robotique.",
            ],
            "bullets": [
                "Conception d'un robot suiveur de ligne sur Arduino avec des capteurs infrarouges",
                "Programmation en C pour une compétition de robotique",
            ],
        },
        {
            "name": "Système de contrôle d'accès RFID",
            "technologies": ["STM32", "RFID", "FreeRTOS"],
            "raw": [
                "contrôle d'accès par badge rfid sur stm32 avec freertos et affichage sur écran lcd",
                "J'ai développé un système de contrôle d'accès par badge RFID sur STM32 (FreeRTOS) avec affichage LCD.",
            ],
            "bullets": [
                "Développement d'un système de contrôle d'accès par badge RFID sur STM32",
                "Utilisation de FreeRTOS et affichage sur écran LCD",
            ],
        },
        {
            "name": "Serre intelligente",
            "technologies": ["Raspberry Pi", "Python"],
            "raw": [
                "serre intelligente avec raspberry pi : arrosage automatique selon l'humidité du sol, code en python",
                "Serre intelligente pilotée par Raspberry Pi avec arrosage automatique selon l'humidité du sol, programmée en Python.",
            ],
            "bullets": [
                "Conception d'une serre intelligente pilotée par Raspberry Pi",
                "Arrosage automatique selon l'humidité du sol, programmé en Python",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire en systèmes embarqués",
            "raw": [
                "j'ai développé des drivers i2c et spi pour des capteurs sur microcontrôleur stm32",
                "Développement de drivers I2C et SPI pour des capteurs sur microcontrôleur STM32.",
            ],
            "bullets": [
                "Développement de drivers I2C et SPI pour des capteurs sur microcontrôleur STM32",
            ],
        },
        {
            "role": "Ingénieur logiciel embarqué",
            "raw": [
                "développement de logiciels embarqués automobiles en c, tests sur banc et communication can",
                "Je développe des logiciels embarqués automobiles en C, avec tests sur banc et communication CAN.",
            ],
            "bullets": [
                "Développement de logiciels embarqués automobiles en C",
                "Tests sur banc et mise en œuvre de la communication CAN",
            ],
        },
        {
            "role": "Stage d'été en électronique",
            "raw": [
                "conception d'une carte électronique sur kicad et tests des prototypes",
                "J'ai conçu une carte électronique sous KiCad et testé les prototypes.",
            ],
            "bullets": [
                "Conception d'une carte électronique sous KiCad",
                "Tests des prototypes",
            ],
        },
    ],
}

TRACKS["bi"] = {
    "fields": ["Business intelligence", "Informatique de gestion", "Systèmes d'information", "Big data"],
    "titles": ["Consultant BI", "Ingénieur data", "Analyste décisionnel"],
    "skills": {
        "BI": ["Power BI", "Talend", "SSIS", "Tableau", "Qlik Sense"],
        "Big Data": ["Spark", "Hadoop", "Airflow", "Kafka"],
        "Bases de données": ["SQL Server", "Oracle", "PostgreSQL", "Snowflake"],
        "Langages": ["SQL", "Python", "DAX", "Scala"],
    },
    "projects": [
        {
            "name": "Entrepôt de données RH",
            "technologies": ["Talend", "SQL Server", "Power BI"],
            "raw": [
                "entrepôt de données rh : etl avec talend vers sql server et rapports power bi sur l'absentéisme",
                "Entrepôt de données RH alimenté par des flux ETL Talend vers SQL Server, avec des rapports Power BI sur l'absentéisme.",
            ],
            "bullets": [
                "Conception d'un entrepôt de données RH sous SQL Server",
                "Développement des flux ETL avec Talend",
                "Création de rapports Power BI sur l'absentéisme",
            ],
        },
        {
            "name": "Pipeline de données temps réel",
            "technologies": ["Kafka", "Spark", "Airflow"],
            "raw": [
                "pipeline de données temps réel avec kafka et spark streaming, orchestré avec airflow",
                "J'ai construit une pipeline de données temps réel (Kafka, Spark Streaming) orchestrée avec Airflow.",
            ],
            "bullets": [
                "Construction d'une pipeline de données temps réel avec Kafka et Spark Streaming",
                "Orchestration des traitements avec Airflow",
            ],
        },
        {
            "name": "Tableau de bord financier",
            "technologies": ["Power BI", "DAX"],
            "raw": [
                "dashboard power bi de suivi du chiffre d'affaires et des marges avec des mesures dax",
                "Tableau de bord Power BI de suivi du chiffre d'affaires et des marges, avec mesures DAX.",
            ],
            "bullets": [
                "Création d'un tableau de bord Power BI de suivi du chiffre d'affaires et des marges",
                "Développement de mesures DAX",
            ],
        },
    ],
    "experiences": [
        {
            "role": "Stagiaire BI",
            "raw": [
                "j'ai développé des flux ssis pour alimenter le datawarehouse et créé des rapports power bi pour les ventes",
                "Développement de flux SSIS d'alimentation du datawarehouse et création de rapports Power BI pour les ventes.",
            ],
            "bullets": [
                "Développement de flux SSIS pour l'alimentation du datawarehouse",
                "Création de rapports Power BI pour les ventes",
            ],
        },
        {
            "role": "Consultant BI junior",
            "raw": [
                "accompagnement de clients sur leurs projets décisionnels, modélisation en étoile et développement de rapports tableau",
                "J'accompagne des clients dans leurs projets décisionnels : modélisation en étoile et développement de rapports Tableau.",
            ],
            "bullets": [
                "Accompagnement de clients dans leurs projets décisionnels",
                "Modélisation en étoile et développement de rapports Tableau",
            ],
        },
        {
            "role": "Data Engineer",
            "raw": [
                "migration des traitements batch vers spark et mise en place de dags airflow",
                "Migration de traitements batch vers Spark et mise en place de DAG Airflow.",
            ],
            "bullets": [
                "Migration des traitements batch vers Spark",
                "Mise en place de DAG Airflow",
            ],
        },
    ],
}

# Profils rédigés par l'utilisateur lui-même (recopiés tels quels).
USER_PROFILES = [
    "Passionné par le développement logiciel, je souhaite mettre mes compétences au service d'une équipe dynamique.",
    "Étudiante motivée et curieuse, à la recherche d'un stage de fin d'études.",
    "Jeune diplômé rigoureux, j'aime résoudre des problèmes complexes et apprendre de nouvelles technologies.",
    "Curieuse et autonome, je m'intéresse particulièrement à l'intelligence artificielle et à la data.",
    "Développeur autodidacte, j'aime concevoir des applications utiles et bien structurées.",
    "À la recherche d'une alternance dans le domaine du cloud et du DevOps.",
    "Je recherche un stage PFE de 6 mois à partir de février.",
    "Ingénieur motivé, orienté qualité et travail en équipe.",
]

# Compétences comportementales (catégorie optionnelle).
SOFT_SKILLS = ["Travail en équipe", "Communication", "Autonomie", "Gestion du temps",
               "Esprit d'analyse", "Adaptabilité", "Leadership", "Résolution de problèmes"]
