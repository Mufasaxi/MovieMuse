from flask import Flask, render_template, request, jsonify
import requests
import openai
import keys
import json
from collections import defaultdict
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    filename=f'moviemuse_{datetime.now().strftime("%Y%m%d")}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

# API Keys
TMDB_API_KEY = keys.TMDB_API_KEY
openai.api_key = keys.OPENAI_API_KEY

def get_openai_analysis(user_preferences):
    """Use OpenAI to analyze user preferences and generate search terms"""
    system_prompt = """You are a movie recommendation expert. Analyze the user's preferences and extract:
    1. Key themes, moods, and specific elements they're looking for
    2. Genre preferences (both explicit and implicit)
    3. Similar movies that closely match these preferences
    4. Any preferences about time period, style, or production quality
    5. Important exclusions or things they want to avoid
    
    Format the response as a JSON object with these keys:
    {
        "search_terms": ["list", "of", "specific", "search", "terms"],
        "genres": ["list", "of", "genre", "ids"],
        "similar_movies": ["movie1", "movie2"],
        "exclude_keywords": ["terms", "to", "avoid"],
        "year_range": {"start": YYYY, "end": YYYY},
        "required_keywords": ["must", "have", "elements"],
        "mood": ["emotional", "tones"],
        "min_rating": float
    }
    
    For genres, use TMDB genre IDs:
    Action: 28, Adventure: 12, Animation: 16, Comedy: 35, Crime: 80,
    Documentary: 99, Drama: 18, Family: 10751, Fantasy: 14, History: 36,
    Horror: 27, Music: 10402, Mystery: 9648, Romance: 10749,
    Science Fiction: 878, TV Movie: 10770, Thriller: 53, War: 10752, Western: 37
    
    IMPORTANT: Always include a year_range with valid start and end years, and all other required fields."""

    default_analysis = {
        "search_terms": [user_preferences],
        "genres": [],
        "similar_movies": [],
        "exclude_keywords": [],
        "year_range": {"start": 1900, "end": 2024},
        "required_keywords": [],
        "mood": [],
        "min_rating": 0
    }

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User preferences: {user_preferences}"}
            ],
            temperature=0.7,
            max_tokens=400
        )
        
        # Parse JSON response
        analysis = json.loads(response.choices[0].message.content)
        
        # Validate and set defaults for missing or invalid values
        validated_analysis = default_analysis.copy()
        validated_analysis.update({
            k: v for k, v in analysis.items() 
            if v is not None and k in default_analysis
        })
        
        # Ensure year_range is properly formatted
        if 'year_range' in analysis and isinstance(analysis['year_range'], dict):
            year_range = analysis['year_range']
            current_year = datetime.now().year
            validated_analysis['year_range'] = {
                'start': max(1900, min(current_year, int(year_range.get('start', 1900)))),
                'end': max(1900, min(current_year, int(year_range.get('end', current_year))))
            }
            
            # Ensure start year is not after end year
            if validated_analysis['year_range']['start'] > validated_analysis['year_range']['end']:
                validated_analysis['year_range']['start'] = validated_analysis['year_range']['end']
        
        logging.info(f"Successfully analyzed preferences: {validated_analysis}")
        return validated_analysis
        
    except Exception as e:
        logging.error(f"Error in OpenAI analysis: {str(e)}")
        return default_analysis

# TODO: Use Movie Overview to improve tailoring of movies for user preferences
def discover_movies(analysis):
    """Discover movies based on complex criteria"""
    try:
        url = 'https://api.themoviedb.org/3/discover/movie'
        
        # Ensure we have valid year range
        year_range = analysis.get('year_range', {"start": 1900, "end": 2024})
        if not isinstance(year_range, dict):
            year_range = {"start": 1900, "end": 2024}
        
        start_year = str(year_range.get('start', 1900))
        end_year = str(year_range.get('end', 2024))
        
        # Validate years are proper integers
        start_year = max(1900, min(2024, int(start_year)))
        end_year = max(1900, min(2024, int(end_year)))
        
        # Ensure start_year isn't after end_year
        if start_year > end_year:
            start_year = end_year
        
        # Handle min_rating safely
        try:
            min_rating = float(analysis.get('min_rating', 0))
            min_rating = max(0, min(10, min_rating))  # Ensure rating is between 0 and 10
        except (TypeError, ValueError):
            min_rating = 0
        
        params = {
            'api_key': TMDB_API_KEY,
            'language': 'en-US',
            'sort_by': 'popularity.desc',
            'include_adult': False,
            'vote_count.gte': 100,
            'vote_average.gte': min_rating,
            'primary_release_date.gte': f"{start_year}-01-01",
            'primary_release_date.lte': f"{end_year}-12-31",
            'with_genres': ','.join(map(str, analysis.get('genres', []))),
            'page': 1
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json().get('results', [])
        logging.info(f"Discovered {len(results)} movies")
        return results
        
    except requests.exceptions.RequestException as e:
        logging.error(f"TMDB API error in discover_movies: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in discover_movies: {str(e)}")
        return []

def search_movies(query):
    """Search for movies based on keywords"""
    try:
        url = f'https://api.themoviedb.org/3/search/movie'
        params = {
            'api_key': TMDB_API_KEY,
            'query': query,
            'language': 'en-US',
            'page': 1
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json().get('results', [])
        logging.info(f"Found {len(results)} movies for query: {query}")
        return results
    except Exception as e:
        logging.error(f"Error in search_movies for query {query}: {str(e)}")
        return []

def get_movie_keywords(movie_id):
    """Get keywords for a specific movie"""
    try:
        url = f'https://api.themoviedb.org/3/movie/{movie_id}/keywords'
        params = {'api_key': TMDB_API_KEY}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return [keyword['name'] for keyword in response.json().get('keywords', [])]
    except Exception as e:
        logging.error(f"Error getting keywords for movie {movie_id}: {str(e)}")
        return []

def calculate_relevance_score(movie, analysis, movie_keywords):
    """Calculate a relevance score for a movie based on user preferences"""
    try:
        score = 0
        
        # Base score from vote average and popularity
        vote_average = float(movie.get('vote_average', 0))
        popularity = float(movie.get('popularity', 0))
        score += (vote_average * 0.5)
        score += (min(popularity, 100) * 0.01)
        
        # Keyword matching
        required_keywords = set(analysis.get('required_keywords', []))
        exclude_keywords = set(analysis.get('exclude_keywords', []))
        movie_keywords = set(movie_keywords)
        
        # Check for required keywords
        if required_keywords:
            matches = required_keywords.intersection(movie_keywords)
            score += (len(matches) / len(required_keywords)) * 5
        
        # Penalize excluded keywords
        if exclude_keywords:
            matches = exclude_keywords.intersection(movie_keywords)
            score -= len(matches) * 2
        
        # Mood matching
        mood_keywords = set(analysis.get('mood', []))
        if mood_keywords:
            matches = mood_keywords.intersection(movie_keywords)
            score += (len(matches) / len(mood_keywords)) * 3
        
        # Year relevance
        year_range = analysis.get('year_range', {"start": 1900, "end": 2024})
        if isinstance(year_range, dict):
            try:
                release_date = movie.get('release_date', '')
                if release_date:
                    year = int(release_date[:4])
                    if year_range['start'] <= year <= year_range['end']:
                        score += 1
            except (ValueError, TypeError, IndexError):
                pass
        
        return max(score, 0)  # Ensure score doesn't go negative
        
    except Exception as e:
        logging.error(f"Error calculating relevance score: {str(e)}")
        return 0

def get_movie_details(movie_id):
    """Get detailed information about a specific movie"""
    try:
        url = f'https://api.themoviedb.org/3/movie/{movie_id}'
        params = {
            'api_key': TMDB_API_KEY,
            'language': 'en-US',
            'append_to_response': 'credits,keywords'
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error getting movie details for {movie_id}: {str(e)}")
        return {}

def process_preferences(preferences):
    """Process user preferences and return relevant movies"""
    try:
        logging.info(f"Processing preferences: {preferences}")
        
        # Get analysis from OpenAI
        analysis = get_openai_analysis(preferences)
        
        all_movies = defaultdict(dict)  # Use movie ID as key to avoid duplicates
        
        # Get movies through discover endpoint
        discovered_movies = discover_movies(analysis)
        for movie in discovered_movies:
            all_movies[movie['id']] = movie
        
        # Search using the generated search terms
        for term in analysis.get('search_terms', [preferences]):
            results = search_movies(term)
            for movie in results:
                all_movies[movie['id']] = movie
        
        # Calculate relevance scores for each movie
        scored_movies = []
        for movie in all_movies.values():
            try:
                keywords = get_movie_keywords(movie['id'])
                relevance_score = calculate_relevance_score(movie, analysis, keywords)
                movie['relevance_score'] = relevance_score
                scored_movies.append(movie)
            except Exception as e:
                logging.error(f"Error processing movie {movie.get('id')}: {str(e)}")
                continue
        
        # Sort by relevance score
        scored_movies.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Log success
        logging.info(f"Successfully processed preferences. Found {len(scored_movies)} movies")
        
        return scored_movies[:10]  # Return top 10 most relevant movies
        
    except Exception as e:
        logging.error(f"Error in process_preferences: {str(e)}")
        # Return a simple search result as fallback
        return search_movies(preferences)[:5]

@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        if request.method == 'POST':
            preferences = request.form.get('preferences', '')
            if not preferences.strip():
                return render_template('index.html', error="Please enter your movie preferences")
            
            movies = process_preferences(preferences)
            
            if not movies:
                return render_template('index.html', 
                    error="No movies found. Please try different preferences")
            
            # Enhance movies with additional details
            enhanced_movies = []
            for movie in movies:
                try:
                    details = get_movie_details(movie['id'])
                    if details:
                        # Add cast information
                        if 'credits' in details:
                            movie['cast'] = [actor['name'] for actor in 
                                details['credits'].get('cast', [])[:3]]
                        # Add keywords
                        if 'keywords' in details:
                            movie['keywords'] = [keyword['name'] for keyword in 
                                details['keywords'].get('keywords', [])[:5]]
                        enhanced_movies.append(movie)
                except Exception as e:
                    logging.error(f"Error enhancing movie {movie.get('id')}: {str(e)}")
                    # Still include the movie even if enhancement fails
                    enhanced_movies.append(movie)
            
            return render_template('results.html', 
                movies=enhanced_movies,
                search_query=preferences)
                
        return render_template('index.html')
        
    except Exception as e:
        logging.error(f"Error in index route: {str(e)}")
        return render_template('index.html', 
            error="An unexpected error occurred. Please try again.")

@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', 
        error="An unexpected error occurred. Please try again."), 500

if __name__ == '__main__':
    app.run(debug=True)