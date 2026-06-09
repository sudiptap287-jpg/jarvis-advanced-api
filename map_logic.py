import folium
import io

class PremiumMapEngine:
    def __init__(self, api_key):
        self.api_key = api_key

    def generate_map_html(self, lat, lon, zoom=13):
        # Premium Feature: Custom Google Tile Layer with your API Key
        google_tiles = f"https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}&key={self.api_key}"
        
        # Initialize Map
        m = folium.Map(
            location=[lat, lon],
            zoom_start=zoom,
            tiles=google_tiles,
            attr='Premium Offline-Ready Map'
        )

        # Add Marker
        folium.Marker([lat, lon], popup="Selected Location").add_to(m)

        # Return as HTML string for your UI/Browser
        data = io.BytesIO()
        m.save(data, close_file=False)
        return data.getvalue().decode()