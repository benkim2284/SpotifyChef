from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from django.urls import reverse

# Create your views here.
def login_view(request):

    return render(request, 'SpotifyWrappedApp/login.html')

def oauth_view(request):
    # Start Spotify OAuth authorization
    sp_oauth = SpotifyOAuth(
        client_id="9833aa7522aa4d8a83682c3acc925ab5",
        client_secret="a6d9a3ee02e644ba83ff34c368001d42",
        redirect_uri="http://localhost:8000/SpotifyWrappedApp/home",
        scope = "user-library-read"
    )

    # Redirect to Spotify authorization URL
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

def home_view(request):
    sp_oauth = SpotifyOAuth(
        client_id="9833aa7522aa4d8a83682c3acc925ab5",
        client_secret="a6d9a3ee02e644ba83ff34c368001d42",
        redirect_uri="http://localhost:8000/SpotifyWrappedApp/home",
        scope = "user-library-read"
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

    # Fetch artist albums
    taylor_uri = 'spotify:artist:3TVXtAsR1Inumwj472S9r4'
    results = sp.artist_top_tracks(taylor_uri)
    top_tracks = results['tracks']

    # Render album names to the template
    return render(request, 'SpotifyWrappedApp/home.html', {'albums': top_tracks})

# New log-out view
def logout_view(request):
    # Remove the access token from the session
    # logout_url = "https://accounts.spotify.com/en/logout"
    # redirect_url = f"{logout_url}?continue={request.build_absolute_uri(reverse('SpotifyWrappedApp:oauth_screen'))}"
    # redirect_url
    return redirect(reverse('SpotifyWrappedApp:login'))