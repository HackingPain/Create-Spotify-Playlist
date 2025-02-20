import requests
import tkinter as tk
from tkinter import messagebox

# Logging setup (optional but recommended for debugging)
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Spotify API functions
def create_playlist(access_token, user_id, playlist_name):
    """
    Creates a new playlist on Spotify for a specified user.
    
    Parameters:
    - access_token (str): Authorization token for Spotify API.
    - user_id (str): Spotify user ID where the playlist will be created.
    - playlist_name (str): Name of the playlist to be created.
    
    Returns:
    - playlist_id (str): ID of the newly created playlist.
    """
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": playlist_name,
        "public": False  # Or True if you want it public
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise exception for HTTP errors
        playlist_data = response.json()
        playlist_id = playlist_data.get("id")
        logging.info(f"Created playlist '{playlist_name}' with ID: {playlist_id}")
        return playlist_id
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating playlist: {e}")
        return None

def add_tracks_to_playlist(access_token, playlist_id, track_uris):
    """
    Adds tracks to an existing playlist on Spotify.
    
    Parameters:
    - access_token (str): Authorization token for Spotify API.
    - playlist_id (str): ID of the playlist where tracks will be added.
    - track_uris (list): List of Spotify track URIs to be added to the playlist.
    
    Returns:
    - success (bool): True if tracks were added successfully, False otherwise.
    """
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "uris": track_uris
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise exception for HTTP errors
        logging.info(f"Added {len(track_uris)} tracks to playlist ID: {playlist_id}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error adding tracks to playlist: {e}")
        return False

# GUI setup using tkinter
class SpotifyPlaylistGUI:
    def __init__(self, master):
        self.master = master
        master.title("Spotify Playlist Manager")
        
        # Labels and Entry fields
        self.label_access_token = tk.Label(master, text="Access Token:")
        self.entry_access_token = tk.Entry(master, width=50)
        self.label_user_id = tk.Label(master, text="User ID:")
        self.entry_user_id = tk.Entry(master, width=50)
        self.label_playlist_name = tk.Label(master, text="Playlist Name:")
        self.entry_playlist_name = tk.Entry(master, width=50)
        self.label_track_uris = tk.Label(master, text="Track URIs (comma-separated):")
        self.entry_track_uris = tk.Entry(master, width=50)
        
        # Buttons
        self.create_playlist_button = tk.Button(master, text="Create Playlist", command=self.create_playlist)
        self.add_tracks_button = tk.Button(master, text="Add Tracks", command=self.add_tracks)
        
        # Layout using grid
        self.label_access_token.grid(row=0, column=0, sticky=tk.W)
        self.entry_access_token.grid(row=0, column=1, padx=10, pady=5, columnspan=2)
        self.label_user_id.grid(row=1, column=0, sticky=tk.W)
        self.entry_user_id.grid(row=1, column=1, padx=10, pady=5, columnspan=2)
        self.label_playlist_name.grid(row=2, column=0, sticky=tk.W)
        self.entry_playlist_name.grid(row=2, column=1, padx=10, pady=5, columnspan=2)
        self.label_track_uris.grid(row=3, column=0, sticky=tk.W)
        self.entry_track_uris.grid(row=3, column=1, padx=10, pady=5, columnspan=2)
        self.create_playlist_button.grid(row=4, column=1, padx=10, pady=10)
        self.add_tracks_button.grid(row=4, column=2, padx=10, pady=10)
    
    def create_playlist(self):
        access_token = self.entry_access_token.get()
        user_id = self.entry_user_id.get()
        playlist_name = self.entry_playlist_name.get()
        
        # Validate inputs
        if not access_token or not user_id or not playlist_name:
            messagebox.showerror("Error", "Please enter Access Token, User ID, and Playlist Name.")
            return
        
        # Create playlist
        playlist_id = create_playlist(access_token, user_id, playlist_name)
        if playlist_id:
            messagebox.showinfo("Success", f"Playlist '{playlist_name}' created successfully with ID: {playlist_id}")
        else:
            messagebox.showerror("Error", "Failed to create playlist. See logs for details.")
    
    def add_tracks(self):
        access_token = self.entry_access_token.get()
        playlist_id = self.entry_user_id.get()  # Using User ID field for Playlist ID in GUI for simplicity
        track_uris_input = self.entry_track_uris.get()
        
        # Validate inputs
        if not access_token or not playlist_id or not track_uris_input:
            messagebox.showerror("Error", "Please enter Access Token, Playlist ID, and Track URIs.")
            return
        
        # Convert track URIs input to list
        track_uris = track_uris_input.split(",")
        
        # Add tracks to playlist
        success = add_tracks_to_playlist(access_token, playlist_id, track_uris)
        if success:
            messagebox.showinfo("Success", f"Added {len(track_uris)} tracks to playlist ID: {playlist_id}")
        else:
            messagebox.showerror("Error", "Failed to add tracks. See logs for details.")

# Initialize GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = SpotifyPlaylistGUI(root)
    root.mainloop()
