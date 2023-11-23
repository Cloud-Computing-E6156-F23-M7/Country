from app import app, db, get_malaria_iso, import_country_data

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        import_country_data()

    app.run()
    