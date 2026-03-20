import requests
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import webbrowser
import http.server
import urllib.parse
import logging
import os
import secrets

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------------------------------------------------------
# Spotify API helpers
# ---------------------------------------------------------------------------

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SCOPES = "playlist-modify-public playlist-modify-private"


def get_current_user(access_token):
    """Fetch the current user's profile (user ID, display name)."""
    url = f"{SPOTIFY_API_BASE}/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("id"), data.get("display_name", data.get("id"))
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching user profile: {e}")
        return None, None


def search_tracks(access_token, query, limit=10):
    """Search Spotify for tracks by name. Returns list of dicts with name, artist, uri."""
    url = f"{SPOTIFY_API_BASE}/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": query, "type": "track", "limit": limit}
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        items = resp.json().get("tracks", {}).get("items", [])
        results = []
        for t in items:
            artists = ", ".join(a["name"] for a in t.get("artists", []))
            results.append({
                "name": t["name"],
                "artist": artists,
                "uri": t["uri"],
                "album": t.get("album", {}).get("name", ""),
            })
        return results
    except requests.exceptions.RequestException as e:
        logging.error(f"Error searching tracks: {e}")
        return []


def create_playlist(access_token, user_id, playlist_name, public=False):
    """Create a new playlist for the given user."""
    url = f"{SPOTIFY_API_BASE}/users/{user_id}/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"name": playlist_name, "public": public}
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        playlist_id = resp.json().get("id")
        logging.info(f"Created playlist '{playlist_name}' with ID: {playlist_id}")
        return playlist_id
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating playlist: {e}")
        return None


def add_tracks_to_playlist(access_token, playlist_id, track_uris):
    """Add a list of track URIs to a playlist."""
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json={"uris": track_uris})
        resp.raise_for_status()
        logging.info(f"Added {len(track_uris)} tracks to playlist {playlist_id}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error adding tracks: {e}")
        return False


# ---------------------------------------------------------------------------
# Local OAuth callback server
# ---------------------------------------------------------------------------

class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Tiny HTTP handler that captures the OAuth authorization code."""

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        code = params.get("code", [None])[0]
        error = params.get("error", [None])[0]

        if code:
            self.server.auth_code = code
            body = b"<html><body><h2>Login successful!</h2><p>You can close this tab and return to the app.</p></body></html>"
        else:
            self.server.auth_code = None
            body = f"<html><body><h2>Login failed</h2><p>{error or 'Unknown error'}</p></body></html>".encode()

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass


def _exchange_code_for_token(code, client_id, client_secret):
    """Exchange an authorization code for an access token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    try:
        resp = requests.post(SPOTIFY_TOKEN_URL, data=data)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except requests.exceptions.RequestException as e:
        logging.error(f"Token exchange failed: {e}")
        return None


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class SpotifyPlaylistGUI:
    def __init__(self, master):
        self.master = master
        master.title("Spotify Playlist Manager")
        master.resizable(False, False)

        self.access_token = None
        self.user_id = None
        self.display_name = None
        self.created_playlist_id = None
        self.search_results = []  # list of dicts from search_tracks()
        self.selected_uris = []   # URIs the user has checked

        # ---------- Frames ----------
        frame_login = ttk.LabelFrame(master, text="1. Log In", padding=10)
        frame_login.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        frame_playlist = ttk.LabelFrame(master, text="2. Create Playlist", padding=10)
        frame_playlist.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        frame_search = ttk.LabelFrame(master, text="3. Search & Add Songs", padding=10)
        frame_search.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        frame_status = ttk.Frame(master, padding=(10, 5))
        frame_status.grid(row=3, column=0, sticky="ew")

        # ---------- 1. Login ----------
        ttk.Label(frame_login, text="Client ID:").grid(row=0, column=0, sticky="w")
        self.entry_client_id = ttk.Entry(frame_login, width=52)
        self.entry_client_id.grid(row=0, column=1, padx=5, pady=2)
        # Pre-fill from env vars if available
        env_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
        if env_id:
            self.entry_client_id.insert(0, env_id)

        ttk.Label(frame_login, text="Client Secret:").grid(row=1, column=0, sticky="w")
        self.entry_client_secret = ttk.Entry(frame_login, width=52, show="*")
        self.entry_client_secret.grid(row=1, column=1, padx=5, pady=2)
        env_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        if env_secret:
            self.entry_client_secret.insert(0, env_secret)

        self.btn_login = ttk.Button(frame_login, text="Log In with Spotify", command=self._start_login)
        self.btn_login.grid(row=2, column=0, columnspan=2, pady=(8, 0))

        self.label_login_status = ttk.Label(frame_login, text="Not logged in", foreground="gray")
        self.label_login_status.grid(row=3, column=0, columnspan=2, pady=(4, 0))

        # ---------- 2. Create Playlist ----------
        ttk.Label(frame_playlist, text="Playlist Name:").grid(row=0, column=0, sticky="w")
        self.entry_playlist_name = ttk.Entry(frame_playlist, width=40)
        self.entry_playlist_name.grid(row=0, column=1, padx=5, pady=2)

        self.var_public = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame_playlist, text="Public", variable=self.var_public).grid(row=0, column=2, padx=5)

        self.btn_create = ttk.Button(frame_playlist, text="Create Playlist", command=self._create_playlist, state="disabled")
        self.btn_create.grid(row=1, column=0, columnspan=3, pady=(8, 0))

        self.label_playlist_status = ttk.Label(frame_playlist, text="", foreground="gray")
        self.label_playlist_status.grid(row=2, column=0, columnspan=3, pady=(4, 0))

        # ---------- 3. Search & Add ----------
        search_row = ttk.Frame(frame_search)
        search_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(search_row, text="Search:").pack(side="left")
        self.entry_search = ttk.Entry(search_row, width=40)
        self.entry_search.pack(side="left", padx=5)
        self.entry_search.bind("<Return>", lambda e: self._do_search())
        self.btn_search = ttk.Button(search_row, text="Search", command=self._do_search, state="disabled")
        self.btn_search.pack(side="left")

        # Results list with checkboxes
        self.results_frame = ttk.Frame(frame_search)
        self.results_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        self.check_vars = []  # BooleanVars for each result row

        self.btn_add_selected = ttk.Button(frame_search, text="Add Selected to Playlist", command=self._add_selected, state="disabled")
        self.btn_add_selected.grid(row=2, column=0, pady=(8, 0))

        # ---------- Status bar ----------
        self.label_status = ttk.Label(frame_status, text="Ready — log in to get started.", foreground="gray")
        self.label_status.grid(row=0, column=0, sticky="w")

    # ---- Login ----

    def _start_login(self):
        client_id = self.entry_client_id.get().strip()
        client_secret = self.entry_client_secret.get().strip()
        if not client_id or not client_secret:
            messagebox.showerror("Error", "Please enter your Client ID and Client Secret.")
            return

        self.label_login_status.config(text="Opening browser...", foreground="blue")
        self.btn_login.config(state="disabled")
        self._set_status("Waiting for Spotify login...")

        # Run OAuth flow in a background thread so the GUI doesn't freeze
        threading.Thread(target=self._oauth_flow, args=(client_id, client_secret), daemon=True).start()

    def _oauth_flow(self, client_id, client_secret):
        state = secrets.token_urlsafe(16)
        auth_url = (
            f"{SPOTIFY_AUTH_URL}?response_type=code"
            f"&client_id={client_id}"
            f"&scope={SCOPES.replace(' ', '%20')}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&state={state}"
        )
        # Start a one-shot local server to capture the redirect
        server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), _OAuthCallbackHandler)
        server.auth_code = None
        server.timeout = 120  # wait up to 2 minutes

        webbrowser.open(auth_url)
        server.handle_request()  # blocks until one request arrives

        code = server.auth_code
        if not code:
            self.master.after(0, self._login_failed, "Login was cancelled or failed.")
            return

        token = _exchange_code_for_token(code, client_id, client_secret)
        if not token:
            self.master.after(0, self._login_failed, "Could not exchange code for token.")
            return

        user_id, display_name = get_current_user(token)
        if not user_id:
            self.master.after(0, self._login_failed, "Could not fetch user profile.")
            return

        # Success — update UI from main thread
        self.master.after(0, self._login_success, token, user_id, display_name)

    def _login_success(self, token, user_id, display_name):
        self.access_token = token
        self.user_id = user_id
        self.display_name = display_name
        self.label_login_status.config(text=f"Logged in as {display_name}", foreground="green")
        self.btn_login.config(state="normal")
        self.btn_create.config(state="normal")
        self.btn_search.config(state="normal")
        self._set_status(f"Welcome, {display_name}! Create a playlist or search for songs.")

    def _login_failed(self, message):
        self.label_login_status.config(text="Login failed", foreground="red")
        self.btn_login.config(state="normal")
        self._set_status(message)
        messagebox.showerror("Login Failed", message)

    # ---- Playlist ----

    def _create_playlist(self):
        name = self.entry_playlist_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a playlist name.")
            return

        self._set_status("Creating playlist...")
        pid = create_playlist(self.access_token, self.user_id, name, public=self.var_public.get())
        if pid:
            self.created_playlist_id = pid
            self.label_playlist_status.config(text=f"Playlist '{name}' created!", foreground="green")
            self.btn_add_selected.config(state="normal")
            self._set_status(f"Playlist '{name}' ready. Search for songs to add!")
        else:
            self.label_playlist_status.config(text="Failed to create playlist.", foreground="red")
            self._set_status("Playlist creation failed — check your credentials.")
            messagebox.showerror("Error", "Failed to create playlist. Check logs for details.")

    # ---- Search ----

    def _do_search(self):
        query = self.entry_search.get().strip()
        if not query:
            return

        self._set_status(f"Searching for '{query}'...")
        results = search_tracks(self.access_token, query)
        self.search_results = results
        self._render_results()
        self._set_status(f"Found {len(results)} results for '{query}'.")

    def _render_results(self):
        # Clear previous results
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()

        if not self.search_results:
            ttk.Label(self.results_frame, text="No results found.", foreground="gray").pack(anchor="w")
            return

        for i, track in enumerate(self.search_results):
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)
            text = f"{track['name']}  —  {track['artist']}  ({track['album']})"
            cb = ttk.Checkbutton(self.results_frame, text=text, variable=var)
            cb.pack(anchor="w", pady=1)

    # ---- Add tracks ----

    def _add_selected(self):
        if not self.created_playlist_id:
            messagebox.showerror("Error", "Create a playlist first.")
            return

        uris = []
        for i, var in enumerate(self.check_vars):
            if var.get():
                uris.append(self.search_results[i]["uri"])

        if not uris:
            messagebox.showwarning("No Selection", "Select at least one song to add.")
            return

        self._set_status(f"Adding {len(uris)} song(s)...")
        ok = add_tracks_to_playlist(self.access_token, self.created_playlist_id, uris)
        if ok:
            self._set_status(f"Added {len(uris)} song(s) to your playlist!")
            messagebox.showinfo("Success", f"Added {len(uris)} song(s) to your playlist!")
            # Uncheck boxes after adding
            for var in self.check_vars:
                var.set(False)
        else:
            self._set_status("Failed to add songs.")
            messagebox.showerror("Error", "Failed to add tracks. Check logs for details.")

    # ---- Helpers ----

    def _set_status(self, text):
        self.label_status.config(text=text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SpotifyPlaylistGUI(root)
    root.mainloop()
