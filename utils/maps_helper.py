"""
utils/maps_helper.py — Google Maps helper + mock hospital fallback
"""

import config

MOCK_HOSPITALS = [
    {"name": "City General Hospital",    "distance": "1.2 km", "rating": 4.3, "open": True,  "lat": 0, "lng": 0},
    {"name": "Apollo Clinic",            "distance": "2.1 km", "rating": 4.6, "open": True,  "lat": 0, "lng": 0},
    {"name": "Government District Hospital","distance":"2.8 km","rating": 3.9, "open": True,  "lat": 0, "lng": 0},
    {"name": "Fortis Hospital",          "distance": "3.4 km", "rating": 4.5, "open": True,  "lat": 0, "lng": 0},
    {"name": "Primary Health Centre",    "distance": "0.8 km", "rating": 4.0, "open": True,  "lat": 0, "lng": 0},
]

def get_maps_api_key():
    return config.GOOGLE_MAPS_API_KEY if not config.DEMO_MAPS else ""

def get_mock_hospitals():
    return MOCK_HOSPITALS
