from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest, JsonResponse
from django.urls import reverse
from dotenv import load_dotenv
import openai
from .models import User, SoloWraps, DuoWraps
from django.core.cache import cache
import os
import json
from django.views.decorators.csrf import csrf_exempt
import requests
import base64
import time
from urllib.parse import urlencode

load_dotenv(dotenv_path='.env')

def login_view(request):
    return render(request, 'SpotifyWrappedApp/login.html')

def oauth_view(request):
    # Start Spotify OAuth authorization
    client_id = os.getenv('client_id')
    redirect_uri = "http://localhost:8000/SpotifyWrappedApp/home"
    scope = "user-library-read user-top-read user-read-email user-read-private"

    auth_url = "https://accounts.spotify.com/authorize"
    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'scope': scope,
        'redirect_uri': redirect_uri
    }
    url = auth_url + '?' + urlencode(auth_params)
    return redirect(url)

def get_access_token(request):
    access_token = request.session.get('access_token')
    refresh_token = request.session.get('refresh_token')
    expires_at = request.session.get('expires_at')
    client_id = os.getenv('client_id')
    client_secret = os.getenv('client_secret')

    if access_token:
        if int(time.time()) > expires_at:
            # Access token expired, refresh it
            token_url = "https://accounts.spotify.com/api/token"
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }
            headers = {
                'Authorization': 'Basic ' + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode(),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            response = requests.post(token_url, data=data, headers=headers)
            if response.status_code != 200:
                return None
            token_info = response.json()
            access_token = token_info['access_token']
            expires_in = token_info['expires_in']
            request.session['access_token'] = access_token
            request.session['expires_at'] = int(time.time()) + expires_in
    else:
        access_token = None

    return access_token

def get_current_user(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get('https://api.spotify.com/v1/me', headers=headers)
    if response.status_code != 200:
        raise Exception("Failed to get current user")
    return response.json()

def get_current_user_top_tracks(access_token, limit=15):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'limit': limit
    }
    response = requests.get('https://api.spotify.com/v1/me/top/tracks', headers=headers, params=params)
    if response.status_code != 200:
        raise Exception("Failed to get current user's top tracks")
    return response.json()

def get_artist(access_token, artist_id):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(f'https://api.spotify.com/v1/artists/{artist_id}', headers=headers)
    if response.status_code != 200:
        raise Exception("Failed to get artist info")
    return response.json()

def get_audio_features(access_token, track_id):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(f'https://api.spotify.com/v1/audio-features/{track_id}', headers=headers)
    if response.status_code != 200:
        raise Exception("Failed to get audio features")
    return response.json()

def friend_select_view(request):
    current_user_id = request.user.id
    users = User.objects.exclude(id=current_user_id)

    return render(request, 'SpotifyWrappedApp/friend_select.html', {'users': users})

@csrf_exempt
def create_duowrap(request):
    try:
        # Step 1: Parse the incoming request
        if request.method != 'POST':
            return HttpResponseBadRequest("Invalid request method. Expected POST.")

        try:
            # Parse the JSON body
            data = json.loads(request.body)
            selected_friend_id = data.get('selected_friend')
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {str(e)}")  # Debugging: Log JSON decoding issues
            return HttpResponseBadRequest("Invalid JSON format.")

        # Step 2: Validate the presence of 'selected_friend'
        if not selected_friend_id:
            print("Debugging: 'selected_friend' key missing or empty")  # Debugging: Log missing friend selection
            return HttpResponseBadRequest("Friend selection not provided.")






        access_token = get_access_token(request)
        if not access_token:
            return HttpResponseBadRequest("Authorization code not provided or token expired.")
        try:
            current_user_info = get_current_user(access_token)
        except Exception as e:
            return HttpResponseBadRequest(str(e))
        curr_user_id = current_user_info['id']

        #Person creating the duo_wrap
        try:
            existing_user = User.objects.get(id=curr_user_id)
        except User.DoesNotExist:
            return HttpResponseBadRequest("User does not exist.")


        # Step 7: Get the selected friend's info from the database
        try:
            friend_user = User.objects.get(id=selected_friend_id)
        except User.DoesNotExist:
            print(f"Debugging: Selected friend with ID {selected_friend_id} does not exist in database")  # Debugging
            return HttpResponseBadRequest("Selected friend not found in database.")

        # Step 8: Set OpenAI API key
        openai.api_key = os.getenv('OPENAI_API_KEY')

        # Step 9: Call OpenAI API to generate duo wrap
        print("Debugging: Calling OpenAI API for duo wrap generation...")  # Debugging
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"""Using the provided track_info data for two users' top 15 songs, generate content for 8 Spotify Wrapped slides.
                            Each slide should focus on one category (e.g., Emotional Track, Favorite Genre, High-Energy Hits, Hidden Gems), and include a fun, creative, in-depth, and medium-length paragraph analysis for each category.
                            Provide engaging text for each slide and include relevant emojis. Your output should be just a JSON that is formatted like '{{"category_name": “analysis...”, "category_name": “analysis...”, ...}}'.
                            Be sure to provide synergies of genres and common songs or anything related between the current user and the selected friend and display according to the format instructed.

                            The track_info data for the current user ({existing_user.name}) is: {existing_user.spotify_data}
                            The track_info data for the selected friend ({friend_user.name}) is: {friend_user.spotify_data}

                            Your output should be just the JSON and nothing else. Make sure to not start your response with '''json or anything.
                            It should start with just the json itself.
                            
                            Also include the last slide to dynamically describe how someone who listens to both my and my duo partner's music tends to get along/act/think/dress kind of like a horoscope.
                            """
                }
            ],
            temperature=0.7
        )

        print("Debugging: OpenAI API call completed successfully.")  # Debugging

        # Step 10: Process OpenAI API response
        raw_reply = response["choices"][0]["message"]["content"]
        try:
            reply = json.loads(raw_reply)
        except json.JSONDecodeError as e:
            print(f"Debugging: JSON Decode Error when parsing OpenAI response: {str(e)}")  # Debugging
            return HttpResponseBadRequest("Invalid response format from OpenAI.")

        # Step 11: Save new DuoWrap
        new_wrap = DuoWraps(
            user_1=existing_user,
            user_2=friend_user,
            wrap_data=reply,
        )
        new_wrap.save()

        # Step 12: Return the wrap ID for redirection
        return JsonResponse({'wrapped_id': new_wrap.unique_id}, status=200)

    except Exception as e:
        # General exception handling to log unexpected errors
        print(f"Debugging: An unexpected error occurred: {str(e)}")  # Debugging
        return HttpResponseBadRequest("An unexpected error occurred.")

@csrf_exempt
def create_solowrap(request):
    access_token = get_access_token(request)
    if not access_token:
        return HttpResponseBadRequest("Authorization code not provided or token expired.")
    try:
        current_user_info = get_current_user(access_token)
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    curr_user_id = current_user_info['id']

    try:
        existing_user = User.objects.get(id=curr_user_id)
    except User.DoesNotExist:
        return HttpResponseBadRequest("User does not exist.")

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
                        Also include the last slide to dynamically describe how someone who listens to my kind of music tends to act/think/dress kind of like a horoscope.
                        """
            }
        ],
        temperature=0.7  # Adjust temperature as needed
    )

    print("done")

    raw_reply = response["choices"][0]["message"]["content"]
    try:
        reply = json.loads(raw_reply)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return JsonResponse({'error': 'Failed to parse AI response'}, status=500)

    new_wrap = SoloWraps(
        user=existing_user,
        wrap_data=reply,
    )
    new_wrap.save()
    return JsonResponse({'wrapped_id': new_wrap.unique_id}, status=200)

def home_view(request):
    code = request.GET.get('code')
    client_id = os.getenv('client_id')
    client_secret = os.getenv('client_secret')
    redirect_uri = "http://localhost:8000/SpotifyWrappedApp/home"
    if code:
        # Exchange the code for an access token
        token_url = "https://accounts.spotify.com/api/token"
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri
        }
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(token_url, data=data, headers=headers)
        if response.status_code != 200:
            return redirect("/SpotifyWrappedApp/home")
            # return HttpResponseBadRequest("Could not retrieve access token.")
        token_info = response.json()
        access_token = token_info['access_token']
        refresh_token = token_info['refresh_token']
        expires_in = token_info['expires_in']
        request.session['access_token'] = access_token
        request.session['refresh_token'] = refresh_token
        request.session['expires_at'] = int(time.time()) + expires_in
    else:
        access_token = get_access_token(request)
        if not access_token:
            return HttpResponseBadRequest("Authorization code not provided or token expired.")

    # Now use access_token to make API calls
    try:
        current_user_info = get_current_user(access_token)
    except Exception as e:
        return HttpResponseBadRequest(str(e))

    curr_user_id = current_user_info['id']
    curr_user_display_name = current_user_info['display_name']

    try:
        results = get_current_user_top_tracks(access_token, limit=15)
    except Exception as e:
        return HttpResponseBadRequest(str(e))

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
        try:
            artist_details = get_artist(access_token, artist_id)
        except Exception as e:
            return HttpResponseBadRequest(str(e))
        genres = artist_details['genres']

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
            # 'audio_features': audio_features if you included them
        }
        top_tracks_with_insights.append(track_info)

    # Save or update the user in the database
    if curr_user_id not in User.objects.values_list('id', flat=True):
        new_existing_user = User(
            id=curr_user_id,
            name=current_user_info["display_name"],
            email=current_user_info["email"],
            spotify_data=top_tracks_with_insights
        )
        new_existing_user.save()
    else:
        new_existing_user = User.objects.get(id=curr_user_id)
        new_existing_user.spotify_data = top_tracks_with_insights
        new_existing_user.save()
        print("User already exists, but top tracks have been updated!")

    # Retrieve existing wraps for the user
    existing_user_wraps = SoloWraps.objects.filter(user=new_existing_user).order_by('-created_at')
    existing_user_duo_wraps = DuoWraps.objects.filter(user_1=new_existing_user) | DuoWraps.objects.filter(user_2=new_existing_user).order_by('-created_at')

    # Render the home view with the relevant information
    return render(request, 'SpotifyWrappedApp/home.html',
                  {
                      'name': curr_user_display_name,
                      "wraps": existing_user_wraps,
                      "duo_wraps": existing_user_duo_wraps
                  })

def wrapped_view(request, wrapped_id):
    curr_solowrap = SoloWraps.objects.get(unique_id=wrapped_id)
    solowrap_date = curr_solowrap.created_at
    user_name = curr_solowrap.user.name
    return render(request, 'SpotifyWrappedApp/wrapped.html', {
        'wrap_data': curr_solowrap.wrap_data,
        "name": user_name,
        "date": solowrap_date
    })

def duo_wrapped_view(request, wrapped_id):
    try:
        curr_duowrap = DuoWraps.objects.get(unique_id=wrapped_id)
    except DuoWraps.DoesNotExist:
        return HttpResponseBadRequest("Duo wrap not found.")

    # Extract relevant information from the duo wrap
    wrap_data = curr_duowrap.wrap_data
    user_1_name = curr_duowrap.user_1.name
    user_2_name = curr_duowrap.user_2.name
    duowrap_date = curr_duowrap.created_at

    # Render the duo_wrapped.html template
    return render(request, 'SpotifyWrappedApp/duo_wrapped.html', {
        'wrap_data': wrap_data,
        'user_1_name': user_1_name,
        'user_2_name': user_2_name,
        'date': duowrap_date
    })


def toptracks_view(request):
    access_token = get_access_token(request)
    if not access_token:
        return HttpResponseBadRequest("Authorization code not provided or token expired.")

    try:
        results = get_current_user_top_tracks(access_token, limit=10)
    except Exception as e:
        return HttpResponseBadRequest(str(e))

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
        try:
            artist_details = get_artist(access_token, artist_id)
        except Exception as e:
            return HttpResponseBadRequest(str(e))
        genres = artist_details['genres']

        track_id = track_stuff['id']
        try:
            audio_features = get_audio_features(access_token, track_id)
        except Exception as e:
            return HttpResponseBadRequest(str(e))

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

    try:
        current_user_info = get_current_user(access_token)
    except Exception as e:
        return HttpResponseBadRequest(str(e))

    if current_user_info["id"] not in User.objects.values_list('id', flat=True):
        new_user = User(
            id=current_user_info["id"],
            name=current_user_info["display_name"],
            email=current_user_info["email"],
            spotify_data=top_tracks_with_insights
        )
        new_user.save()
    else:
        print("User already exists!!!")

    return render(request, 'SpotifyWrappedApp/toptracks.html', {'albums': top_tracks_with_insights, "analysis": "reply"})

def logout_view(request):
    # Remove the access token from the session
    request.session.flush()
    return redirect(reverse('SpotifyWrappedApp:login_screen'))

@csrf_exempt
def create_holidaywrap(request, holiday):
    access_token = get_access_token(request)
    if not access_token:
        return HttpResponseBadRequest("Authorization code not provided or token expired.")

    try:
        current_user_info = get_current_user(access_token)
    except Exception as e:
        return HttpResponseBadRequest(str(e))
    curr_user_id = current_user_info['id']

    try:
        existing_user = User.objects.get(id=curr_user_id)
    except User.DoesNotExist:
        return HttpResponseBadRequest("User does not exist.")

    openai.api_key = os.getenv('OPENAI_API_KEY')

    print(f"Calling holiday wrap for {holiday}")

    # Modify the prompt based on the holiday
    if holiday.lower() == 'christmas':
        prompt = f"""Using the provided track_info data for the user's top 15 songs, generate content for 8 Spotify Wrapped slides with a Christmas theme.
Each slide should focus on one category (e.g., Emotional Track, Favorite Genre, High-Energy Hits, Hidden Gems), and include a fun, creative, in-depth, and medium-length paragraph analysis for each category.
Provide engaging text for each slide and include relevant Christmas emojis and references. Your output should be just a JSON formatted like '{{"category_name": "analysis...", "category_name": "analysis...", ...}}'.

The track_info data for the user’s top 15 songs is: {existing_user.spotify_data}

Your output should be just the JSON and nothing else. Make sure to not start your response with ```json or anything.
It should start with just the JSON itself.
If the JSON output has no christmas related songs however, ignore this and artificially populate the responses with random christmas songs.
Also include the last slide to dynamically describe how someone who listens to my kind of music tends to act/think/dress kind of like a horoscope.
"""
    elif holiday.lower() == 'halloween':
        prompt = f"""Using the provided track_info data for the user's top 15 songs, generate content for 8 Spotify Wrapped slides with a Halloween theme.
Each slide should focus on one category (e.g., Spooky Tracks, Favorite Genre, High-Energy Hits, Hidden Gems), and include a fun, creative, in-depth, and medium-length paragraph analysis for each category.
Provide engaging text for each slide and include relevant Halloween emojis and references. Your output should be just a JSON formatted like '{{"category_name": "analysis...", "category_name": "analysis...", ...}}'.

The track_info data for the user’s top 15 songs is: {existing_user.spotify_data}

Your output should be just the JSON and nothing else. Make sure to not start your response with ```json or anything.
It should start with just the JSON itself.

If the JSON output has no halloween related songs however, ignore this and artificially populate the responses with random halloween songs.
Also include the last slide to dynamically describe how someone who listens to my kind of music tends to act/think/dress kind of like a horoscope.
"""
    else:
        return HttpResponseBadRequest("Invalid holiday.")

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7  # Adjust temperature as needed
    )

    print("done")

    raw_reply = response["choices"][0]["message"]["content"]

    try:
        reply = json.loads(raw_reply)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return JsonResponse({'error': 'Failed to parse AI response'}, status=500)

    new_wrap = SoloWraps(
        user=existing_user,
        wrap_data=reply,
    )
    new_wrap.save()
    return JsonResponse({'wrapped_id': new_wrap.unique_id}, status=200)

def guessTop(request):
    code = request.GET.get('code')
    client_id = os.getenv('client_id')
    client_secret = os.getenv('client_secret')
    redirect_uri = "http://localhost:8000/SpotifyWrappedApp/home"
    if code:
        # Exchange the code for an access token
        token_url = "https://accounts.spotify.com/api/token"
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri
        }
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(token_url, data=data, headers=headers)
        if response.status_code != 200:
            return redirect("/SpotifyWrappedApp/home")
            # return HttpResponseBadRequest("Could not retrieve access token.")
        token_info = response.json()
        access_token = token_info['access_token']
        refresh_token = token_info['refresh_token']
        expires_in = token_info['expires_in']
        request.session['access_token'] = access_token
        request.session['refresh_token'] = refresh_token
        request.session['expires_at'] = int(time.time()) + expires_in
    else:
        access_token = get_access_token(request)
        if not access_token:
            return HttpResponseBadRequest("Authorization code not provided or token expired.")

    try:
        results = get_current_user_top_tracks(access_token, limit=15)
        top_tracks = results['items']  # List of track objects

        if not top_tracks:
            return HttpResponseBadRequest("No top tracks found.")

        # Prepare a list of tracks with necessary information
        tracks_info = []
        for track in top_tracks:
            track_info = {
                'id': track['id'],
                'name': track['name'],
                'album_art_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'artists': [artist['name'] for artist in track['artists']],
            }
            tracks_info.append(track_info)

        # Remove tracks without album art
        tracks_with_art = [track for track in tracks_info if track['album_art_url']]

        if not tracks_with_art:
            return HttpResponseBadRequest("No tracks with available album art.")

        # Serialize the tracks data to JSON to pass to the template
        tracks_json = json.dumps(tracks_with_art)

        return render(request, 'SpotifyWrappedApp/guessTop.html', {
            'tracks_json': tracks_json
        })

    except Exception as e:
        return HttpResponseBadRequest(f"Spotify Exception while fetching top tracks: {e}")

