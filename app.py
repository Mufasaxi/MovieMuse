from flask import Flask, render_template, request
import requests
from transformers import RagTokenizer, RagRetriever, RagSequenceForGeneration
import keys

app = Flask(__name__)

TMDB_API_KEY = keys.TMDB_API_KEY

# Initialize the RAG model components
tokenizer = RagTokenizer.from_pretrained("facebook/rag-sequence-nq")
retriever = RagRetriever.from_pretrained("facebook/rag-sequence-nq", dataset="wiki_dpr", index_name="compressed")
rag_model = RagSequenceForGeneration.from_pretrained("facebook/rag-sequence-nq")

def get_movie_data(movie_id):
    """Fetch movie details from the TMDb API"""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}'
    response = requests.get(url)
    return response.json()

def get_rag_recommendations(preferences):
    """Generate movie recommendations using the RAG model"""
    # Prepare the input for the RAG model
    input_ids = tokenizer.encode(preferences, return_tensors="pt")

    # Generate the movie recommendations using the RAG model
    output = rag_model.generate(input_ids, max_length=50, num_return_sequences=5)

    # Process the RAG model output and extract the movie recommendations
    recommendations = [tokenizer.decode(seq, skip_special_tokens=True) for seq in output]
    return recommendations

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get user preferences from the form
        preferences = request.form['preferences']

        # Use the RAG model to get movie recommendations
        movie_recommendations = get_rag_recommendations(preferences)

        # Fetch additional movie details from the TMDb API
        movies = [get_movie_data(m) for m in movie_recommendations]

        return render_template('results.html', movies=movies)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)