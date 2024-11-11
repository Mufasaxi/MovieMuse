from flask import Flask, render_template, request
import requests
import openai
import keys
import json

app = Flask(__name__)

# API Keys
TMDB_API_KEY = keys.TMDB_API_KEY
openai.api_key = keys.OPENAI_API_KEY

def get_openai_analysis(user_preferences):
    """Use OpenAI to analyze user preferences and generate search terms"""
    system_prompt = """You are a movie recommendation expert. Analyze the user's movie preferences and extract:
    1. Key themes or genres
    2. Important elements (like "plot twists", "character development", etc.)
    3. Similar popular movies that match these preferences
    
    Format the response as a JSON object with these keys:
    {
        "search_terms": ["list", "of", "search", "terms"],
        "genres": ["list", "of", "genres"],
        "similar_movies": ["movie1", "movie2"]
    }
    Keep each list to 3-5 items maximum."""

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User preferences: {user_preferences}"}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        # Parse JSON response
        analysis = json.loads(response.choices[0].message.content)
        return analysis
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return {
            "search_terms": [user_preferences],
            "genres": [],
            "similar_movies": []
        }

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
    return response.json().get('results', [])

def get_movie_recommendations(movie_id):
    """Get movie recommendations based on a movie ID"""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/recommendations'
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'page': 1
    }
    response = requests.get(url, params=params)
    return response.json().get('results', [])

def search_by_similar_movie(movie_name):
    """Search for a movie by name and get its recommendations"""
    initial_search = search_movies(movie_name)
    if initial_search:
        return get_movie_recommendations(initial_search[0]['id'])
    return []

def process_preferences(preferences):
    """Process user preferences using OpenAI and return relevant movies"""
    # Get analysis from OpenAI
    analysis = get_openai_analysis(preferences)
    
    all_movies = []
    seen_ids = set()

    # Search using the generated search terms
    for term in analysis['search_terms']:
        results = search_movies(term)
        for movie in results:
            if movie['id'] not in seen_ids:
                seen_ids.add(movie['id'])
                all_movies.append(movie)

    # Get recommendations based on similar movies
    for movie_name in analysis.get('similar_movies', []):
        similar_movies = search_by_similar_movie(movie_name)
        for movie in similar_movies:
            if movie['id'] not in seen_ids:
                seen_ids.add(movie['id'])
                all_movies.append(movie)

    # Sort movies by popularity and rating
    all_movies.sort(key=lambda x: (x.get('vote_average', 0) * x.get('popularity', 0)), reverse=True)
    
    return all_movies[:5]  # Return top 5 unique movies

def get_movie_details(movie_id):
    """Get detailed information about a specific movie"""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}'
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'append_to_response': 'credits,keywords'
    }
    response = requests.get(url, params=params)
    return response.json()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        preferences = request.form['preferences']
        movies = process_preferences(preferences)
        
        # Enhance movies with additional details
        enhanced_movies = []
        for movie in movies:
            details = get_movie_details(movie['id'])
            # Add cast information
            if 'credits' in details:
                movie['cast'] = [actor['name'] for actor in details['credits'].get('cast', [])[:3]]
            # Add keywords
            if 'keywords' in details:
                movie['keywords'] = [keyword['name'] for keyword in details['keywords'].get('keywords', [])[:5]]
            enhanced_movies.append(movie)
            
        return render_template('results.html', movies=enhanced_movies)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)