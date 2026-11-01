import pytest

COLUMNS = [
    "realSum", "room_shared", "room_private", "person_capacity", "multi", "biz", "cleanliness_rating",
    "guest_satisfaction_overall", "bedrooms", "dist", "metro_dist", "attr_index", "attr_index_norm",
    "rest_index", "rest_index_norm", "lng", "lat",
    "room_type_Entire home/apt", "room_type_Private room", "room_type_Shared room",
    "city_amsterdam", "city_athens", "city_barcelona", "city_berlin", "city_budapest",
    "city_lisbon", "city_london", "city_paris", "city_rome", "city_vienna",
    "day_type_weekdays", "day_type_weekends",
]

LISTINGS = [
    {"realSum": 172.77, "room_type": "Private room", "room_shared": False, "room_private": True,
     "person_capacity": 2.0, "multi": 0, "biz": 0, "cleanliness_rating": 10.0, "guest_satisfaction_overall": 93.0,
     "bedrooms": 1, "dist": 1.22, "metro_dist": 0.40, "attr_index": 550.08, "attr_index_norm": 12.19,
     "rest_index": 1075.41, "rest_index_norm": 23.43, "lng": 12.50181, "lat": 41.88987,
     "city": "rome", "day_type": "weekends"},
    {"realSum": 250.57, "room_type": "Entire home/apt", "room_shared": False, "room_private": False,
     "person_capacity": 3.0, "multi": 1, "biz": 0, "cleanliness_rating": 10.0, "guest_satisfaction_overall": 99.0,
     "bedrooms": 1, "dist": 1.73, "metro_dist": 0.21, "attr_index": 118.65, "attr_index_norm": 8.50,
     "rest_index": 185.10, "rest_index_norm": 4.42, "lng": 16.365, "lat": 48.223,
     "city": "vienna", "day_type": "weekdays"},
    {"realSum": 98.10, "room_type": "Shared room", "room_shared": True, "room_private": False,
     "person_capacity": 4.0, "multi": 0, "biz": 1, "cleanliness_rating": 8.0, "guest_satisfaction_overall": 80.0,
     "bedrooms": 1, "dist": 3.10, "metro_dist": 0.90, "attr_index": 300.00, "attr_index_norm": 10.00,
     "rest_index": 500.00, "rest_index_norm": 12.00, "lng": 4.90569, "lat": 52.41772,
     "city": "amsterdam", "day_type": "weekdays"},
]


@pytest.fixture
def columns() -> list[str]:
    return list(COLUMNS)


@pytest.fixture
def listings() -> list[dict]:
    return [dict(listing) for listing in LISTINGS]
