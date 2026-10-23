
from math import radians, sin, cos, asin, sqrt


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate the distance between two GPS coordinates in kilometers."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    return 6371.0 * 2 * asin(sqrt(min(1.0, a)))


def overlaps(start_a, end_a, start_b, end_b) -> bool:
    """Return True if two rental date ranges overlap."""
    return start_a < end_b and start_b < end_a


def top_k_nearest(
    vehicles,
    latitude: float,
    longitude: float,
    k: int = 5,
):
    """Return the k nearest vehicles that have GPS coordinates."""
    if k <= 0:
        return []

    results = []

    for vehicle in vehicles:
        if vehicle.latitude is None or vehicle.longitude is None:
            continue

        distance = haversine_km(
            latitude,
            longitude,
            vehicle.latitude,
            vehicle.longitude,
        )

        index = 0

        while (
            index < len(results)
            and results[index][0] <= distance
        ):
            index += 1

        results.insert(index, (distance, vehicle))

        if len(results) > k:
            results.pop()

    return [
        {
            "distance_km": round(distance, 2),
            "vehicle": vehicle,
        }
        for distance, vehicle in results
    ]
