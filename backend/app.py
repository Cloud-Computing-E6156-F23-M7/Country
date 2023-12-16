import json, os, requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import pandas as pd

### Set up the database ###

class DbConfig(object):
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://admin:weareteamm7@malariastat.czmrkezas6nx.us-east-2.rds.amazonaws.com:3306/Country_db'
    SQLALCHEMY_BINDS = {
        'country_db': SQLALCHEMY_DATABASE_URI  # default bind
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

app = Flask(__name__)
app.config.from_object(DbConfig)
app.json.sort_keys = False
db = SQLAlchemy(app)
CORS(app)

class Country(db.Model):
    __bind_key__ = 'country_db'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.JSON)
    iso2 = db.Column(db.String(2))
    iso = db.Column(db.String(3))    # assume uppercase
    currencies = db.Column(db.JSON)
    capital = db.Column(db.JSON)
    capitalInfo = db.Column(db.JSON)
    latlng = db.Column(db.JSON)
    area = db.Column(db.Integer)
    population = db.Column(db.Integer)
    timezones = db.Column(db.JSON)
    flags = db.Column(db.JSON)

    def serialize(self):
        return {
            'country_id': self.id,
            'name': self.name,
            'iso2': self.iso2,
            'iso': self.iso,
            'currencies': self.currencies,
            'capital': self.capital,
            'capitalInfo': self.capitalInfo,
            'latlng': self.latlng,
            'area': self.area,
            'population': self.population,
            'timezones': self.timezones,
            'flags': self.flags
        }

### Import data to the database ###

def get_malaria_iso():
    malaria_csv_path = os.path.join(
        os.getcwd(), 
        'estimated_numbers.csv'
        )
    df = pd.read_csv(malaria_csv_path)

    return df['iso'].unique().tolist()   

def import_country_data():
    if Country.query.first():
        return  "Country data already exists in the database"
    
    api_url = 'https://restcountries.com/v3.1/alpha?codes='
    fields = '&fields=name,cca2,cca3,currencies,capital,capitalInfo,latlng,area,population,timezones,flags'
    iso_list_str = ','.join(get_malaria_iso())

    try:
        response = requests.get(api_url + iso_list_str + fields)
        
        if response.status_code == 200:
            api_data = response.json()

            for country in api_data:
                new_country = Country(
                    name=country.get('name'),
                    iso2=country.get('cca2'),
                    iso=country.get('cca3'),   # assume uppercase
                    currencies=country.get('currencies'),
                    capital=country.get('capital'),
                    capitalInfo=country.get('capitalInfo'),
                    latlng=country.get('latlng'),
                    area=country.get('area'),
                    population=country.get('population'),
                    timezones=country.get('timezones'),
                    flags=country.get('flags')
                )
                db.session.add(new_country)
                
            try:
                db.session.commit()
            except (IntegrityError, SQLAlchemyError):
                db.session.rollback()
                return "Error importing country data to the database"
        else:
            return jsonify({
                'error': f'Error fetching country data from API. Status code: {response.status_code}'
                })
    
    except requests.RequestException as e:
        return jsonify({'error': f'Error making API request: {str(e)}'})

# NOTE: This route is needed for the default EB health check route
@app.route('/')  
def home():
    return "Ok"

### Reset database ###

@app.route('/api/reset/country/', methods=['PUT'])
def reset_country_db():
    engine = db.engines['country_db']
    if engine:
        metadata = db.MetaData()
        metadata.reflect(bind=engine)
        metadata.drop_all(bind=engine)
        metadata.create_all(bind=engine)
        import_country_data()
        return "Successfully reset the country database"
    else:
        return "Error resetting the country database", 501

### Country resource ###

@app.route('/api/country/')
def get_country():
    iso = request.args.get('iso')

    query = Country.query

    if iso:
        iso_list = iso.upper().split(',')
        query = query.filter(Country.iso.in_(iso_list))

    return jsonify([country.serialize() for country in query])

@app.route('/api/country/<int:id>/')
def get_country_by_id(id):
    country = db.session.get(Country, id)

    if country:
        return jsonify(country.serialize())
    else:
        return "Country not found", 404

@app.route('/api/country/iso/<string:iso>/')
def get_country_by_iso(iso):
    country = Country.query.filter_by(iso=iso.upper()).first()

    if country:
        return jsonify(country.serialize())
    else:
        return "Country not found", 404

@app.route('/api/country/<int:id>/', methods=['DELETE'])
def delete_country(id):
    country = db.session.get(Country, id)

    if country:
        db.session.delete(country)
        try:
            db.session.commit()
            return "Successfully deleted country data"
        except (IntegrityError, SQLAlchemyError):
            db.session.rollback()
            return "Error deleting country data", 501
    else:
        return "Country not found", 404

@app.route('/api/country/<int:id>/', methods=['PUT'])
def update_country(id):
    country = db.session.get(Country, id)

    if country:
        new_country = request.get_json()
        country.name = new_country.get('name', country.name)
        country.iso2 = new_country.get('iso2', country.iso2)
        country.iso = new_country.get('iso3', country.iso)
        country.currencies = new_country.get('currencies', country.currencies)
        country.capital = new_country.get('capital', country.capital)
        country.capitalInfo = new_country.get('capitalInfo', country.capitalInfo)
        country.latlng = new_country.get('latlng', country.latlng)
        country.area = new_country.get('area', country.area)
        country.population = new_country.get('population', country.population)
        country.timezones = new_country.get('timezones', country.timezones)
        country.flags = new_country.get('flags', country.flags)

        try:
            db.session.commit()
            return "Successfully updated country data"
        except (IntegrityError, SQLAlchemyError):
            db.session.rollback()
            return "Error updating country data", 501
    else:
        return "Country not found", 404

@app.route('/api/country/', methods=['POST'])
def add_country():
    new_country_data = request.get_json()

    new_country = Country(
        name=new_country_data.get('name'),
        iso2=new_country_data.get('iso2'),
        iso=new_country_data.get('iso'),
        currencies=new_country_data.get('currencies'),
        capital=new_country_data.get('capital'),
        capitalInfo=new_country_data.get('capitalInfo'),
        latlng=new_country_data.get('latlng'),
        area=new_country_data.get('area'),
        population=new_country_data.get('population'),
        timezones=new_country_data.get('timezones'),
        flags=new_country_data.get('flags')
    )

    db.session.add(new_country)
    try:
        db.session.commit()
        return "Successfully added country data"
    except (IntegrityError, SQLAlchemyError):
        db.session.rollback()
        return "Error adding country data", 501

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        import_country_data()

    app.run(debug=True, port=7070)
