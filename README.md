# Spotify Playlist Manager

The Spotify Playlist Manager is a Python script and GUI application that interacts with the Spotify Web API to create playlists and add tracks to them.

## Features

- **Create Playlist:** Create a new private Spotify playlist.
- **Add Tracks:** Add specified tracks to an existing Spotify playlist.

## Prerequisites

Before using this application, ensure you have the following:

- **Python:** Version 3.6 or higher installed.
- **Dependencies:** Install necessary Python packages using `pip`:

  pip install requests  

## Setup

1. **Obtain Spotify API Credentials:**
   - Create a Spotify Developer account and register your application to obtain:
     - Client ID
     - Client Secret
     - Redirect URI (for future enhancements)

2. **Configure Environment Variables:**
   - Store your Spotify Client ID and Client Secret securely as environment variables:
   
     export SPOTIFY_CLIENT_ID='your_client_id'
     export SPOTIFY_CLIENT_SECRET='your_client_secret'

3. **Run the Application:**
   - Execute the Python script `spotify_playlist_manager.py`:
   
     python spotify_playlist_manager.py     

## Usage

### GUI Application

- Launch the GUI by running `spotify_playlist_manager.py`.
- Fill in the required fields (`Access Token`, `User ID`, `Playlist Name`, `Track URIs`).
- Click `Create Playlist` to create a new playlist.
- Click `Add Tracks` to add tracks to an existing playlist.

### Command Line Interface (CLI)

- For batch operations or scripting, use the functions `create_playlist` and `add_tracks_to_playlist` directly in your Python scripts.

## Examples

### Creating a Playlist

access_token = "your_access_token_here"
user_id = "your_spotify_user_id_here"
playlist_name = "2000-2004 Hits"
playlist_id = create_playlist(access_token, user_id, playlist_name)
print(f"Created playlist '{playlist_name}' with ID: {playlist_id}")

### Adding Tracks to a Playlist

access_token = "your_access_token_here"
playlist_id = "playlist_id_here"
track_uris = [
    "spotify:track:4uLU6hMCjMI75M1A2tKUQC",
    "spotify:track:another_track_uri_here"
]
success = add_tracks_to_playlist(access_token, playlist_id, track_uris)
if success:
    print(f"Added {len(track_uris)} tracks to playlist ID: {playlist_id}")
else:
    print("Failed to add tracks.")

## Logging

- Detailed logs are captured in the console (`stdout`) using Python's `logging` module. Adjust logging levels (`INFO`, `ERROR`) as needed for debugging.

## Troubleshooting

- Ensure all required fields (`Access Token`, `User ID`, `Playlist Name`, `Track URIs`) are correctly filled before performing operations.
- Check the console for detailed error messages in case of failures.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Spotify Web API documentation for providing guidelines on API usage.

