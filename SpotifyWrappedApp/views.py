from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from django.urls import reverse
import os
from dotenv import load_dotenv
import openai

load_dotenv(dotenv_path='.env')
# Create your views here.
def login_view(request):

    return render(request, 'SpotifyWrappedApp/login.html')

def oauth_view(request):
    # Start Spotify OAuth authorization
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv('client_id'),
        client_secret=os.getenv('client_secret'),
        redirect_uri="http://localhost:8000/SpotifyWrappedApp/home",
        scope = "user-library-read user-top-read"
    )

    # Redirect to Spotify authorization URL
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

def home_view(request):
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv('client_id'),
        client_secret=os.getenv('client_secret'),
        redirect_uri="http://localhost:8000/SpotifyWrappedApp/home",
        scope = "user-library-read user-top-read"
    )

    # Check if there's a 'code' parameter in the request
    code = request.GET.get('code')
    print(code)
    if not code:
        return HttpResponseBadRequest("Authorization code not provided.")

    # Get access token using the authorization code
    token_info = sp_oauth.get_access_token(code)
    if not token_info:
        return HttpResponseBadRequest("Could not retrieve access token.")
    print(f"Token Info: {token_info}")

    if 'access_token' in token_info:
        access_token = token_info['access_token']
        print("Access Token:", access_token)
        print("Token Scopes:", token_info.get('scope'))

    # Create a Spotify client with the obtained token
    sp = Spotify(auth=token_info['access_token'])


    results = sp.current_user_top_tracks()

    print(results['items'][0])

    top_tracks = []

    for track_stuff in results['items']:
        track_info = {
            'name': track_stuff['name'],
            'artist': track_stuff['artists'][0]['name'],  # Primary artist
            'album': track_stuff['album']['name'],
            'image_url': track_stuff['album']['images'][0]['url'],
            'release_date': track_stuff['album']['release_date'],
            'popularity': track_stuff['popularity'],
            'preview_url': track_stuff['preview_url'],
            'track_url': track_stuff['external_urls']['spotify']
        }
        top_tracks.append(track_info)

    openai.api_key = os.getenv('OPENAI_API_KEY')

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"Given my top played songs in spotify, give me a 8-part distinct \
        summary of my music taste, and make it creative {top_tracks}"}
        ],
        temperature=0.7  # Adjust temperature as needed
    )

    # Extract and print the response content
    reply = response["choices"][0]["message"]["content"]

    return render(request, 'SpotifyWrappedApp/home.html', {'albums': top_tracks, "analysis": reply})

# New log-out view
def logout_view(request):
    # Remove the access token from the session
    logout_url = "https://accounts.spotify.com/en/logout"
    redirect_url = f"{logout_url}?continue={request.build_absolute_uri(reverse('SpotifyWrappedApp:oauth_screen'))}"
    return redirect(redirect_url)