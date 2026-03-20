# Spotify Playlist Manager

A simple desktop app to create Spotify playlists and add songs by searching — no technical knowledge required.

## How It Works

1. **Log in** — Click "Log In with Spotify", your browser opens, you approve, done.
2. **Create a playlist** — Type a name, click "Create Playlist".
3. **Search for songs** — Type a song or artist name, check the ones you want, click "Add Selected".

That's it!

## Setup (One-Time)

### 1. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**.
3. Set the **Redirect URI** to `http://localhost:8888/callback` and save.
4. Copy your **Client ID** and **Client Secret**.

### 2. Install Python

Make sure you have [Python 3.6+](https://www.python.org/downloads/) installed.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. (Optional) Set Environment Variables

You can pre-fill the login fields by setting these:

```bash
export SPOTIFY_CLIENT_ID='your_client_id'
export SPOTIFY_CLIENT_SECRET='your_client_secret'
```

On Windows:
```cmd
set SPOTIFY_CLIENT_ID=your_client_id
set SPOTIFY_CLIENT_SECRET=your_client_secret
```

## Running the App

```bash
python spotifyplaylist.py
```

## Features

- **One-click login** — Built-in OAuth flow opens your browser automatically.
- **Search by song name** — No need to know Spotify URIs.
- **Checkbox selection** — Pick songs from search results visually.
- **Auto-detects your account** — No need to look up your User ID.
- **Public or private playlists** — Your choice.

## Using as a Library

You can also use the functions directly in your own scripts:

```python
from spotifyplaylist import create_playlist, add_tracks_to_playlist, search_tracks

# Create a playlist
playlist_id = create_playlist(access_token, user_id, "My Playlist")

# Search for tracks
results = search_tracks(access_token, "bohemian rhapsody")

# Add tracks
uris = [r["uri"] for r in results[:3]]
add_tracks_to_playlist(access_token, playlist_id, uris)
```

## Troubleshooting

- **"Login failed"** — Make sure your Client ID/Secret are correct and your Redirect URI is set to `http://localhost:8888/callback` in the Spotify Developer Dashboard.
- **Browser doesn't open** — Copy the URL from the console and open it manually.
- **Port 8888 in use** — Close other apps using that port, or wait a moment and try again.

## License

MIT License — see [LICENSE](LICENSE) for details.
