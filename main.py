import streamlit as st
import pandas as pd
import json
import requests
from typing import Tuple, List, Optional, Union

# Load API key
with open('API_KEY.txt', 'r') as f:
    API_KEY = json.load(f)['API-KEY']

def geocode_api(zipcode: str) -> Tuple[Optional[List[str]], Optional[Tuple[float, float]], Optional[str]]:
    base_url = f"https://maps.googleapis.com/maps/api/geocode/json?key={API_KEY}&components=postal_code:{zipcode}"
    
    r = requests.get(base_url)
    if r.status_code not in range(200, 299):
        return None, None, None
    
    result = r.json().get('results', [{}])[0]
    
    city_name = next((comp['long_name'] for comp in result.get('address_components', []) 
                      if 'locality' in comp.get('types', [])), None)
    
    localities = result.get('postcode_localities')
    lat = result.get('geometry', {}).get('location', {}).get('lat')
    lng = result.get('geometry', {}).get('location', {}).get('lng')
    
    if localities and city_name:
        localities = [el for el in localities if city_name.lower() not in el.lower()]
    
    return localities, (lat, lng) if lat and lng else None, city_name

def get_place_details(place_id: str) -> Tuple[str, str, str]:
    place_details_endpoint = 'https://maps.googleapis.com/maps/api/place/details/json'
    params = {
        'key': API_KEY,
        'placeid': place_id,
        'language': 'en'
    }
    r = requests.get(place_details_endpoint, params=params)
    result = r.json().get('result', {})
    
    phone_number = result.get('international_phone_number', '-')
    opening_hours = '\n'.join(result.get('opening_hours', {}).get('weekday_text', [])) or '-'
    url = result.get('url', '-')
    
    return phone_number, opening_hours, url

def get_places_df(url_queries: Union[str, List[str]]) -> pd.DataFrame:
    if isinstance(url_queries, str):
        url_queries = [url_queries]
    
    all_places = []
    
    for query in url_queries:
        r = requests.get(query)
        results = r.json().get('results', [])
        
        for place in results:
            place_id = place.get('place_id')
            if place_id not in [p['place_id'] for p in all_places]:
                phone_number, opening_hours, url = get_place_details(place_id)
                all_places.append({
                    'Place': place.get('name', ''),
                    'Ratings': place.get('rating', '-'),
                    'TotalRatings': place.get('user_ratings_total', '-'),
                    'Address': place.get('formatted_address', ''),
                    'Phone Number': phone_number,
                    'Opening Hours': opening_hours,
                    'URL': url,
                    'place_id': place_id
                })
    
    df = pd.DataFrame(all_places)
    df = df.drop(columns=['place_id'])
    return df

st.set_page_config(page_title="Google Maps Places Scraper", page_icon="🗺️", layout="wide")
st.title("Google Maps Places Scraper")
st.subheader("Please enter input details below")

with st.form("input_form"):
    st.warning('Please enter only any one of ZIP Code / Area. Do not enter both as it may produce incorrect results.')
    zip_code = st.text_input("ZIP Code or Post Code:", help="You can enter multiple ZIP Codes separated by a space between them, for example: 10001 10009")
    area = st.text_input("Area:", help="Please enter the area in this format -> Area Name City Name", value="Notting Hill London")
    keyword = st.text_input("Search Keyword:", value='construction')
    submit = st.form_submit_button("Submit")

if submit:
    zip_code = zip_code.strip()
    area = area.strip()

    if zip_code and area:
        st.error('Please enter only any one of Area / ZIP Code.')
    elif zip_code:
        all_query_list = []
        for zip in zip_code.split():
            localities, coordinates, city_name = geocode_api(zip)
            if not coordinates:
                st.error(f'🚨 Error: Cannot find Localities and Coordinates for given ZIP Code: {zip}. Please try using a different ZIP.')
                continue
            
            latitude, longitude = coordinates
            search_query = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={keyword}&location={latitude},{longitude}&key={API_KEY}"
            all_query_list.append(search_query)
            
            if localities:
                for locality in localities:
                    query = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={keyword}+{locality}+{city_name}&key={API_KEY}"
                    all_query_list.append(query)
        
        places_df = get_places_df(all_query_list)
    else:
        query_input = f'{keyword}+{"+".join(area.split())}'
        query_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={query_input}&key={API_KEY}"
        places_df = get_places_df(query_url)

    if not places_df.empty:
        st.write(places_df)
        csv = places_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label='📥 Download Current Result',
            data=csv,
            file_name='Scraped_Places.csv',
            mime='text/csv',
        )
    else:
        st.warning("No results found for the given input.")
