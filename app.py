from flask import Flask, render_template, request
import requests
import keys

app = Flask(__name__)

TMDB_API_KEY = keys.TMDB_API_KEY

def search_movies(query):
    """Search for movies based on keywords"""
    url = f'https://api.themoviedb.org/3/search/movie'
    params = {
        'api_key': TMDB_API_KEY,
        'query': query,
        'language': 'en-US',
        'page': 1
    }
    response = requests.get(url, params=params)
    return response.json().get('results', [])[:5]  # Return top 5 results

def get_movie_recommendations(movie_id):
    """Get movie recommendations based on a movie ID"""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/recommendations'
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'page': 1
    }
    response = requests.get(url, params=params)
    return response.json().get('results', [])[:5]  # Return top 5 recommendations

def get_movie_details(movie_id):
    """Get detailed information about a specific movie"""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}'
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US'
    }
    response = requests.get(url, params=params)
    return response.json()

def process_preferences(preferences):
    """Process user preferences and return relevant movies"""
    # First, search for movies matching the preferences
    initial_results = search_movies(preferences)
    
    if not initial_results:
        return []
    
    # Get recommendations based on the top result
    top_movie_id = initial_results[0]['id']
    recommendations = get_movie_recommendations(top_movie_id)
    
    # Combine initial results with recommendations
    all_movies = initial_results + recommendations
    
    # Remove duplicates based on movie ID
    seen_ids = set()
    unique_movies = []
    for movie in all_movies:
        if movie['id'] not in seen_ids:
            seen_ids.add(movie['id'])
            unique_movies.append(movie)
    
    return unique_movies[:5]  # Return top 5 unique movies

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        preferences = request.form['preferences']
        movies = process_preferences(preferences)
        return render_template('results.html', movies=movies)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)