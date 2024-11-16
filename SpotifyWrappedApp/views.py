from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from django.urls import reverse
from dotenv import load_dotenv
import openai
from .models import User, SoloWraps
from django.core.cache import cache
import os
import json

load_dotenv(dotenv_path='.env')

def login_view(request):
    return render(request, 'SpotifyWrappedApp/login.html')

def oauth_view(request):
    # Start Spotify OAuth authorization
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv('client_id'),
        client_secret=os.getenv('client_secret'),
        redirect_uri="http://localhost:8000/SpotifyWrappedApp/home",
        scope = "user-library-read user-top-read user-read-email"
    )

    # Redirect to Spotify authorization URL
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


def get_authorization_code():
    cache_file_path = '.cache'  # Replace with the actual path to your .cache file

    if not os.path.exists(cache_file_path):
        return None
    else:
        with open(cache_file_path, 'r') as file:
            cached_data = json.load(file)
        return cached_data["access_token"]

def home_view(request):
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv('client_id'),
        client_secret=os.getenv('client_secret'),
        redirect_uri="http://localhost:8000/SpotifyWrappedApp/home",
        scope = "user-library-read user-top-read user-read-email"
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


    results = sp.current_user_top_tracks(limit=15)

    top_tracks_with_insights = []

    for track_stuff in results['items']:
        name = track_stuff['name']
        artist = track_stuff['artists'][0]['name']
        album = track_stuff['album']['name']
        image_url = track_stuff['album']['images'][0]['url']
        release_date = track_stuff['album']['release_date']
        popularity = track_stuff['popularity']
        preview_url = track_stuff['preview_url']
        track_url = track_stuff['external_urls']['spotify']

        artist_id = track_stuff['artists'][0]['id']
        artist_details = sp.artist(artist_id)
        genres = artist_details['genres']

        track_id = track_stuff['id']
        audio_features = sp.audio_features(track_id)[0]
        acousticness = audio_features['acousticness']
        danceability = audio_features['danceability']
        duration_ms = audio_features['duration_ms']
        energy = audio_features['energy']
        instrumentalness = audio_features['instrumentalness']
        liveness = audio_features['liveness']
        loudness = audio_features['loudness']
        speechiness = audio_features['speechiness']
        tempo = audio_features['tempo']
        valence = audio_features['valence']

        track_info = {
            'name': name,
            'artist': artist,
            'genre': genres,
            'album': album,
            'image_url': image_url,
            'release_date': release_date,
            'popularity': popularity,
            'preview_url': preview_url,
            'track_url': track_url,
            'audio_features': {
                'danceability': danceability,
                'energy': energy,
                'loudness': loudness,
                'speechiness': speechiness,
                'acousticness': acousticness,
                'valence': valence,
                'tempo': tempo,
                'duration_ms': duration_ms,
                'instrumentalness': instrumentalness,
                'liveness': liveness
            }
        }
        top_tracks_with_insights.append(track_info)


    current_user_info = sp.current_user()
    curr_user_id = current_user_info['id']
    curr_user_display_name = current_user_info['display_name']

    if curr_user_id not in User.objects.values_list('id', flat=True):
        new_existing_user = User(
            id=curr_user_id,
            name=current_user_info["display_name"],
            email=current_user_info["email"],
            spotify_data= top_tracks_with_insights
        )
        new_existing_user.save()
    else:
        new_existing_user = User.objects.get(id=curr_user_id)
        new_existing_user.spotify_data = top_tracks_with_insights
        new_existing_user.save()
        print("user already exists, but top tracks have been updated!!!")

    existing_user_wraps = SoloWraps.objects.filter(user=new_existing_user)
    print(existing_user_wraps)
    return render(request, 'SpotifyWrappedApp/home.html',
                  {
                      'name': curr_user_display_name,
                      "wraps": existing_user_wraps
                  })



def wrapped_view(request):
    access_token = get_authorization_code()

    if access_token is None:
        return HttpResponseBadRequest("Authorization code not provided.")

    sp = Spotify(auth=access_token)

    current_user_info = sp.current_user()
    curr_user_id = current_user_info['id']
    curr_user_display_name = current_user_info['display_name']

    existing_user = User.objects.get(id=curr_user_id)

    openai.api_key = os.getenv('OPENAI_API_KEY')

    print("calling")
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": f"""Using the provided track_info data for the user's top 15 songs, generate content for 8 Spotify Wrapped slides. 
                    Each slide should focus on one category (e.g., Emotional Track, Favorite Genre, High-Energy Hits, Hidden Gems), and include a fun, creative, in-depth, and medium-length paragraph analysis for each category. 
                    Provide engaging text for each slide and include relevant emojis. Your output should be just a JSON that is formatted like '{{"category_name": “analysis...”, "category_name": “analysis...”, ...}}'. 

                    The track_info data for the user’s top 15 songs is: {existing_user.spotify_data}

                    Your output should be just the JSON and nothing else. Make sure to not start your response with '''json or anything. 
                    It should start with just the json itself.
                    """
            }
        ],
        temperature=0.7  # Adjust temperature as needed
    )

    print("done")

    raw_reply = response["choices"][0]["message"]["content"]
    reply = json.loads(raw_reply)

    new_wrap = SoloWraps(
        user=existing_user,
        wrap_data=reply,
    )
    new_wrap.save()

    return render(request, 'SpotifyWrappedApp/wrapped.html',
                  {
                      'name': curr_user_display_name,
                      "wrap_data": reply
                  })

def toptracks_view(request):
    sp_oauth = SpotifyOAuth(
        client_id=os.getenv('client_id'),
        client_secret=os.getenv('client_secret'),
        redirect_uri="http://localhost:8000/SpotifyWrappedApp/toptracks",
        scope = "user-library-read user-top-read user-read-email"
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




    results = sp.current_user_top_tracks(limit=10)

    top_tracks_with_insights = []

    for track_stuff in results['items']:
        name = track_stuff['name']
        artist = track_stuff['artists'][0]['name']
        album = track_stuff['album']['name']
        image_url = track_stuff['album']['images'][0]['url']
        release_date = track_stuff['album']['release_date']
        popularity = track_stuff['popularity']
        preview_url = track_stuff['preview_url']
        track_url = track_stuff['external_urls']['spotify']

        artist_id = track_stuff['artists'][0]['id']
        artist_details = sp.artist(artist_id)
        genres = artist_details['genres']

        track_id = track_stuff['id']
        audio_features = sp.audio_features(track_id)[0]
        acousticness = audio_features['acousticness']
        danceability = audio_features['danceability']
        duration_ms = audio_features['duration_ms']
        energy = audio_features['energy']
        instrumentalness = audio_features['instrumentalness']
        liveness = audio_features['liveness']
        loudness = audio_features['loudness']
        speechiness = audio_features['speechiness']
        tempo = audio_features['tempo']
        valence = audio_features['valence']

        track_info = {
            'name': name,
            'artist': artist,
            'genre': genres,
            'album': album,
            'image_url': image_url,
            'release_date': release_date,
            'popularity': popularity,
            'preview_url': preview_url,
            'track_url': track_url,
            'audio_features': {
                'danceability': danceability,
                'energy': energy,
                'loudness': loudness,
                'speechiness': speechiness,
                'acousticness': acousticness,
                'valence': valence,
                'tempo': tempo,
                'duration_ms': duration_ms,
                'instrumentalness': instrumentalness,
                'liveness': liveness
            }
        }
        top_tracks_with_insights.append(track_info)


    current_user_info = sp.current_user()

    if current_user_info["id"] not in User.objects.values_list('id', flat=True):
        new_user = User(
            id=current_user_info["id"],
            name=current_user_info["display_name"],
            email=current_user_info["email"],
            spotify_data= top_tracks_with_insights
        )
        new_user.save()
    else:
        print("user already exists!!!")












    openai.api_key = os.getenv('OPENAI_API_KEY')

    # response = openai.ChatCompletion.create(
    #     model="gpt-4o-mini",
    #     messages=[
    #         {"role": "user", "content": f"Given my top played songs in spotify, give me a 8-part distinct \
    #     summary of my music taste, and make it creative {top_tracks}"}
    #     ],
    #     temperature=0.7  # Adjust temperature as needed
    # )
    #
    # reply = response["choices"][0]["message"]["content"]

    return render(request, 'SpotifyWrappedApp/toptracks.html', {'albums': top_tracks_with_insights, "analysis": "reply"})

# New log-out view
def logout_view(request):
    # Remove the access token from the session
    logout_url = "https://accounts.spotify.com/en/logout"
    redirect_url = f"{logout_url}?continue={request.build_absolute_uri(reverse('SpotifyWrappedApp:oauth_screen'))}"
    return redirect(redirect_url)