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
import json

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

CONFIG_PATH = os.path.expanduser("~/.spotify_playlist_config.json")


# ---------------------------------------------------------------------------
# Persistent credentials helpers
# ---------------------------------------------------------------------------

def _load_config():
    """Load saved credentials from the config file, if it exists."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_config(client_id, client_secret):
    """Save Client ID and Client Secret to the config file."""
    config = {"client_id": client_id, "client_secret": client_secret}
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        logging.info("Credentials saved to config file.")
    except OSError as e:
        logging.error(f"Failed to save config: {e}")


# ---------------------------------------------------------------------------
# Error parsing helper
# ---------------------------------------------------------------------------

def _parse_api_error(e):
    """Extract a user-friendly message from a requests exception."""
    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
        status_code = e.response.status_code
        if status_code == 401:
            return "Your session has expired. Please log in again."
        elif status_code == 403:
            return "You don't have permission to modify this playlist."
        elif status_code == 404:
            return "Playlist not found."
        elif status_code == 429:
            return "Too many requests. Please wait a moment and try again."
        else:
            try:
                body = e.response.json()
                error_obj = body.get("error", {})
                message = error_obj.get("message", "") if isinstance(error_obj, dict) else str(error_obj)
                if message:
                    return f"Spotify API error ({status_code}): {message}"
            except (ValueError, AttributeError):
                pass
            return f"Spotify API error ({status_code}): {e}"
    elif isinstance(e, requests.exceptions.ConnectionError):
        return "Could not connect to Spotify. Please check your internet connection."
    elif isinstance(e, requests.exceptions.Timeout):
        return "The request to Spotify timed out. Please try again."
    else:
        return f"An unexpected error occurred: {e}"


# ---------------------------------------------------------------------------
# Spotify API functions
# ---------------------------------------------------------------------------

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
    """Search Spotify for tracks. Returns list of dicts with name, artist, uri, album, preview_url."""
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
                "preview_url": t.get("preview_url"),
            })
        return results
    except requests.exceptions.RequestException as e:
        logging.error(f"Error searching tracks: {e}")
        raise


def create_playlist(access_token, user_id, playlist_name, public=False):
    """Create a new playlist for the given user."""
    url = f"{SPOTIFY_API_BASE}/users/{user_id}/playlists"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"name": playlist_name, "public": public}
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        playlist_id = resp.json().get("id")
        logging.info(f"Created playlist '{playlist_name}' with ID: {playlist_id}")
        return playlist_id
    except requests.exceptions.RequestException as e:
        logging.error(f"Error creating playlist: {e}")
        raise


def add_tracks_to_playlist(access_token, playlist_id, track_uris):
    """Add a list of track URIs to a playlist."""
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json={"uris": track_uris})
        resp.raise_for_status()
        logging.info(f"Added {len(track_uris)} tracks to playlist {playlist_id}")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error adding tracks: {e}")
        raise


def get_user_playlists(access_token):
    """Fetch the current user's playlists. Returns list of {name, id}."""
    url = f"{SPOTIFY_API_BASE}/me/playlists"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(url, headers=headers, params={"limit": 50})
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [{"name": p["name"], "id": p["id"]} for p in items]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching playlists: {e}")
        return []


def get_playlist_tracks(access_token, playlist_id):
    """Fetch tracks in a playlist. Returns list of {name, artist, uri}."""
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(url, headers=headers, params={"limit": 100})
        resp.raise_for_status()
        items = resp.json().get("items", [])
        results = []
        for item in items:
            t = item.get("track")
            if not t:
                continue
            artists = ", ".join(a["name"] for a in t.get("artists", []))
            results.append({"name": t["name"], "artist": artists, "uri": t["uri"]})
        return results
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching playlist tracks: {e}")
        return []


def reorder_playlist_tracks(access_token, playlist_id, range_start, insert_before):
    """Move a single track within a playlist."""
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"range_start": range_start, "insert_before": insert_before, "range_length": 1}
    try:
        resp = requests.put(url, headers=headers, json=payload)
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Error reordering tracks: {e}")
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
        self.search_results = []
        self.playlist_tracks = []       # current tracks in the active playlist
        self.user_playlists = []        # list of {name, id} from API
        self.songs_added_count = 0

        saved_config = _load_config()

        # ---------- Frames ----------
        frame_login = ttk.LabelFrame(master, text="1. Log In", padding=10)
        frame_login.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        frame_playlist = ttk.LabelFrame(master, text="2. Create or Pick a Playlist", padding=10)
        frame_playlist.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        frame_search = ttk.LabelFrame(master, text="3. Search & Add Songs", padding=10)
        frame_search.grid(row=2, column=0, padx=10, pady=5, sticky="ew")

        frame_status = ttk.Frame(master, padding=(10, 5))
        frame_status.grid(row=3, column=0, sticky="ew")

        # ---------- 1. Login ----------
        ttk.Label(frame_login, text="Client ID:").grid(row=0, column=0, sticky="w")
        self.entry_client_id = ttk.Entry(frame_login, width=52)
        self.entry_client_id.grid(row=0, column=1, padx=5, pady=2)
        env_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
        prefill_id = saved_config.get("client_id", "") or env_id
        if prefill_id:
            self.entry_client_id.insert(0, prefill_id)

        ttk.Label(frame_login, text="Client Secret:").grid(row=1, column=0, sticky="w")
        self.entry_client_secret = ttk.Entry(frame_login, width=52, show="*")
        self.entry_client_secret.grid(row=1, column=1, padx=5, pady=2)
        env_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        prefill_secret = saved_config.get("client_secret", "") or env_secret
        if prefill_secret:
            self.entry_client_secret.insert(0, prefill_secret)

        self.var_remember = tk.BooleanVar(value=bool(saved_config.get("client_id")))
        ttk.Checkbutton(frame_login, text="Remember credentials", variable=self.var_remember).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.btn_login = ttk.Button(frame_login, text="Log In with Spotify", command=self._start_login)
        self.btn_login.grid(row=3, column=0, columnspan=2, pady=(8, 0))

        self.label_login_status = ttk.Label(frame_login, text="Not logged in", foreground="gray")
        self.label_login_status.grid(row=4, column=0, columnspan=2, pady=(4, 0))

        # ---------- 2. Playlist ----------
        # Create new
        create_row = ttk.Frame(frame_playlist)
        create_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(create_row, text="New playlist:").pack(side="left")
        self.entry_playlist_name = ttk.Entry(create_row, width=30)
        self.entry_playlist_name.pack(side="left", padx=5)
        self.var_public = tk.BooleanVar(value=False)
        ttk.Checkbutton(create_row, text="Public", variable=self.var_public).pack(side="left", padx=2)
        self.btn_create = ttk.Button(create_row, text="Create", command=self._create_playlist, state="disabled")
        self.btn_create.pack(side="left", padx=5)

        # Or pick existing
        ttk.Label(frame_playlist, text="\u2014 or pick an existing playlist \u2014", foreground="gray").grid(
            row=1, column=0, pady=(6, 2))
        pick_row = ttk.Frame(frame_playlist)
        pick_row.grid(row=2, column=0, sticky="ew")
        self.combo_playlists = ttk.Combobox(pick_row, state="disabled", width=45)
        self.combo_playlists.pack(side="left", padx=5)
        self.combo_playlists.bind("<<ComboboxSelected>>", self._on_playlist_selected)
        self.btn_refresh_playlists = ttk.Button(pick_row, text="Refresh", command=self._refresh_playlists, state="disabled")
        self.btn_refresh_playlists.pack(side="left")

        self.label_playlist_status = ttk.Label(frame_playlist, text="", foreground="gray")
        self.label_playlist_status.grid(row=3, column=0, pady=(4, 0))

        # Playlist contents + reorder
        contents_frame = ttk.Frame(frame_playlist)
        contents_frame.grid(row=4, column=0, sticky="ew", pady=(5, 0))

        self.label_track_count = ttk.Label(contents_frame, text="", foreground="gray")
        self.label_track_count.pack(anchor="w")

        list_and_buttons = ttk.Frame(contents_frame)
        list_and_buttons.pack(fill="x")

        self.listbox_tracks = tk.Listbox(list_and_buttons, height=5, width=55, selectmode=tk.SINGLE)
        tracks_scrollbar = ttk.Scrollbar(list_and_buttons, orient="vertical", command=self.listbox_tracks.yview)
        self.listbox_tracks.config(yscrollcommand=tracks_scrollbar.set)
        self.listbox_tracks.pack(side="left", fill="x", expand=True)
        tracks_scrollbar.pack(side="left", fill="y")

        reorder_btns = ttk.Frame(list_and_buttons)
        reorder_btns.pack(side="left", padx=5)
        self.btn_move_up = ttk.Button(reorder_btns, text="Move Up", command=self._move_track_up, state="disabled", width=10)
        self.btn_move_up.pack(pady=2)
        self.btn_move_down = ttk.Button(reorder_btns, text="Move Down", command=self._move_track_down, state="disabled", width=10)
        self.btn_move_down.pack(pady=2)

        # ---------- 3. Search & Add ----------
        search_row = ttk.Frame(frame_search)
        search_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(search_row, text="Search:").pack(side="left")
        self.entry_search = ttk.Entry(search_row, width=34)
        self.entry_search.pack(side="left", padx=5)
        self.entry_search.bind("<Return>", lambda e: self._do_search())
        self.btn_search = ttk.Button(search_row, text="Search", command=self._do_search, state="disabled")
        self.btn_search.pack(side="left")
        self.btn_batch = ttk.Button(search_row, text="Batch Add", command=self._open_batch_dialog, state="disabled")
        self.btn_batch.pack(side="left", padx=5)

        # Scrollable results area
        results_container = ttk.Frame(frame_search)
        results_container.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        self.results_canvas = tk.Canvas(results_container, height=200, highlightthickness=0)
        self.results_scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=self.results_canvas.yview)
        self.results_frame = ttk.Frame(self.results_canvas)

        self.results_frame.bind(
            "<Configure>",
            lambda e: self.results_canvas.configure(scrollregion=self.results_canvas.bbox("all")))

        self.results_canvas_window = self.results_canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        self.results_canvas.configure(yscrollcommand=self.results_scrollbar.set)
        self.results_canvas.pack(side="left", fill="both", expand=True)
        self.results_scrollbar.pack(side="right", fill="y")

        self.results_canvas.bind("<Enter>", self._bind_mousewheel)
        self.results_canvas.bind("<Leave>", self._unbind_mousewheel)
        self.results_canvas.bind("<Configure>", self._on_canvas_configure)

        self.check_vars = []

        bottom_row = ttk.Frame(frame_search)
        bottom_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.btn_add_selected = ttk.Button(bottom_row, text="Add Selected to Playlist", command=self._add_selected, state="disabled")
        self.btn_add_selected.pack(side="left")
        self.label_added_count = ttk.Label(bottom_row, text="", foreground="green")
        self.label_added_count.pack(side="left", padx=10)

        # ---------- Status bar ----------
        self.label_status = ttk.Label(frame_status, text="Ready \u2014 log in to get started.", foreground="gray")
        self.label_status.grid(row=0, column=0, sticky="w")

    # ---- Scrollable results helpers ----

    def _on_canvas_configure(self, event):
        self.results_canvas.itemconfig(self.results_canvas_window, width=event.width)

    def _bind_mousewheel(self, event):
        self.results_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.results_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.results_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, event):
        self.results_canvas.unbind_all("<MouseWheel>")
        self.results_canvas.unbind_all("<Button-4>")
        self.results_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        self.results_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.results_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.results_canvas.yview_scroll(1, "units")

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
        server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), _OAuthCallbackHandler)
        server.auth_code = None
        server.timeout = 120
        webbrowser.open(auth_url)
        server.handle_request()

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
        self.master.after(0, self._login_success, token, user_id, display_name, client_id, client_secret)

    def _login_success(self, token, user_id, display_name, client_id=None, client_secret=None):
        self.access_token = token
        self.user_id = user_id
        self.display_name = display_name
        self.label_login_status.config(text=f"Logged in as {display_name}", foreground="green")
        self.btn_login.config(state="normal")
        self.btn_create.config(state="normal")
        self.btn_search.config(state="normal")
        self.btn_batch.config(state="normal")
        self.combo_playlists.config(state="readonly")
        self.btn_refresh_playlists.config(state="normal")
        self._set_status(f"Welcome, {display_name}! Create a playlist or search for songs.")

        if self.var_remember.get() and client_id and client_secret:
            _save_config(client_id, client_secret)

        self._refresh_playlists()

    def _login_failed(self, message):
        self.label_login_status.config(text="Login failed", foreground="red")
        self.btn_login.config(state="normal")
        self._set_status(message)
        messagebox.showerror("Login Failed", message)

    # ---- Playlist ----

    def _refresh_playlists(self):
        self.user_playlists = get_user_playlists(self.access_token)
        names = [p["name"] for p in self.user_playlists]
        self.combo_playlists["values"] = names
        if names:
            self.combo_playlists.set("")

    def _on_playlist_selected(self, event):
        idx = self.combo_playlists.current()
        if idx < 0:
            return
        pl = self.user_playlists[idx]
        self.created_playlist_id = pl["id"]
        self.label_playlist_status.config(text=f"Using '{pl['name']}'", foreground="green")
        self.btn_add_selected.config(state="normal")
        self.btn_move_up.config(state="normal")
        self.btn_move_down.config(state="normal")
        self._set_status(f"Selected playlist '{pl['name']}'. Search for songs to add!")
        self._refresh_playlist_contents()

    def _create_playlist(self):
        name = self.entry_playlist_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a playlist name.")
            return
        self._set_status("Creating playlist...")
        try:
            pid = create_playlist(self.access_token, self.user_id, name, public=self.var_public.get())
            if pid:
                self.created_playlist_id = pid
                self.label_playlist_status.config(text=f"Playlist '{name}' created!", foreground="green")
                self.btn_add_selected.config(state="normal")
                self.btn_move_up.config(state="normal")
                self.btn_move_down.config(state="normal")
                self._set_status(f"Playlist '{name}' ready. Search for songs to add!")
                self._refresh_playlists()
                self._refresh_playlist_contents()
        except requests.exceptions.RequestException as e:
            error_msg = _parse_api_error(e)
            self.label_playlist_status.config(text="Failed to create playlist.", foreground="red")
            self._set_status("Playlist creation failed.")
            messagebox.showerror("Error", error_msg)

    def _refresh_playlist_contents(self):
        """Fetch and display current tracks in the active playlist."""
        if not self.created_playlist_id:
            return
        self.playlist_tracks = get_playlist_tracks(self.access_token, self.created_playlist_id)
        self.listbox_tracks.delete(0, tk.END)
        for t in self.playlist_tracks:
            self.listbox_tracks.insert(tk.END, f"{t['name']}  \u2014  {t['artist']}")
        self.label_track_count.config(text=f"Current tracks ({len(self.playlist_tracks)}):")

    # ---- Reorder ----

    def _move_track_up(self):
        sel = self.listbox_tracks.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        if reorder_playlist_tracks(self.access_token, self.created_playlist_id, idx, idx - 1):
            self._refresh_playlist_contents()
            self.listbox_tracks.selection_set(idx - 1)
            self.listbox_tracks.see(idx - 1)
        else:
            messagebox.showerror("Error", "Failed to reorder. Check logs.")

    def _move_track_down(self):
        sel = self.listbox_tracks.curselection()
        if not sel or sel[0] >= len(self.playlist_tracks) - 1:
            return
        idx = sel[0]
        if reorder_playlist_tracks(self.access_token, self.created_playlist_id, idx, idx + 2):
            self._refresh_playlist_contents()
            self.listbox_tracks.selection_set(idx + 1)
            self.listbox_tracks.see(idx + 1)
        else:
            messagebox.showerror("Error", "Failed to reorder. Check logs.")

    # ---- Search ----

    def _do_search(self):
        query = self.entry_search.get().strip()
        if not query:
            return
        self._set_status(f"Searching for '{query}'...")
        try:
            results = search_tracks(self.access_token, query)
            self.search_results = results
            self._render_results()
            self._set_status(f"Found {len(results)} results for '{query}'.")
        except requests.exceptions.RequestException as e:
            error_msg = _parse_api_error(e)
            self.search_results = []
            self._render_results()
            self._set_status("Search failed.")
            messagebox.showerror("Search Error", error_msg)

    def _render_results(self):
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()

        if not self.search_results:
            ttk.Label(self.results_frame, text="No results found.", foreground="gray").pack(anchor="w")
            return

        for i, track in enumerate(self.search_results):
            row = ttk.Frame(self.results_frame)
            row.pack(anchor="w", fill="x", pady=1)

            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)
            text = f"{track['name']}  \u2014  {track['artist']}  ({track['album']})"
            cb = ttk.Checkbutton(row, text=text, variable=var)
            cb.pack(side="left")

            # Preview button
            preview_url = track.get("preview_url")
            if preview_url:
                btn = ttk.Button(row, text="\u25B6", width=3,
                                 command=lambda url=preview_url: webbrowser.open(url))
                btn.pack(side="right", padx=2)
            else:
                lbl = ttk.Label(row, text="no preview", foreground="gray")
                lbl.pack(side="right", padx=2)

        self.results_canvas.yview_moveto(0)

    # ---- Add tracks ----

    def _add_selected(self):
        if not self.created_playlist_id:
            messagebox.showerror("Error", "Create or select a playlist first.")
            return

        uris = []
        names = []
        for i, var in enumerate(self.check_vars):
            if var.get():
                uris.append(self.search_results[i]["uri"])
                names.append(self.search_results[i]["name"])

        if not uris:
            messagebox.showwarning("No Selection", "Select at least one song to add.")
            return

        # Duplicate detection
        existing_uris = {t["uri"] for t in self.playlist_tracks}
        dupes = [names[i] for i, u in enumerate(uris) if u in existing_uris]
        if dupes:
            dupe_list = "\n".join(f"  - {n}" for n in dupes)
            proceed = messagebox.askyesno(
                "Duplicates Found",
                f"These songs are already in the playlist:\n{dupe_list}\n\nAdd them anyway?")
            if not proceed:
                return

        self._set_status(f"Adding {len(uris)} song(s)...")
        try:
            add_tracks_to_playlist(self.access_token, self.created_playlist_id, uris)
            self.songs_added_count += len(uris)
            self._set_status(f"Added {len(uris)} song(s)! Keep searching to add more.")
            self.label_added_count.config(text=f"{self.songs_added_count} songs added so far")
            for var in self.check_vars:
                var.set(False)
            self._refresh_playlist_contents()
        except requests.exceptions.RequestException as e:
            error_msg = _parse_api_error(e)
            self._set_status("Failed to add songs.")
            messagebox.showerror("Error", error_msg)

    # ---- Batch Add ----

    def _open_batch_dialog(self):
        dialog = tk.Toplevel(self.master)
        dialog.title("Batch Add Songs")
        dialog.resizable(False, False)
        dialog.grab_set()

        ttk.Label(dialog, text="Paste song names (one per line):").pack(anchor="w", padx=10, pady=(10, 2))

        text_widget = tk.Text(dialog, width=50, height=12)
        text_widget.pack(padx=10, pady=5)

        results_frame = ttk.Frame(dialog)
        results_frame.pack(fill="x", padx=10)

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        matches = []  # will hold (song_name, matched_track_or_None)

        def do_search_all():
            for widget in results_frame.winfo_children():
                widget.destroy()
            matches.clear()

            lines = text_widget.get("1.0", tk.END).strip().split("\n")
            lines = [l.strip() for l in lines if l.strip()]
            if not lines:
                return

            for line in lines:
                try:
                    results = search_tracks(self.access_token, line, limit=1)
                except requests.exceptions.RequestException:
                    results = []

                row_frame = ttk.Frame(results_frame)
                row_frame.pack(anchor="w", fill="x", pady=1)

                if results:
                    match = results[0]
                    matches.append((line, match))
                    ttk.Label(row_frame, text=f"{line}  \u2192  {match['name']} \u2014 {match['artist']}",
                              foreground="green").pack(side="left")
                else:
                    matches.append((line, None))
                    ttk.Label(row_frame, text=f"{line}  \u2192  no match found",
                              foreground="red").pack(side="left")

            btn_add_all.config(state="normal")

        def do_add_all():
            if not self.created_playlist_id:
                messagebox.showerror("Error", "Create or select a playlist first.")
                return
            uris = [m["uri"] for _, m in matches if m is not None]
            if not uris:
                messagebox.showwarning("No Matches", "No songs were matched.")
                return
            try:
                add_tracks_to_playlist(self.access_token, self.created_playlist_id, uris)
                self.songs_added_count += len(uris)
                self.label_added_count.config(text=f"{self.songs_added_count} songs added so far")
                self._refresh_playlist_contents()
                self._set_status(f"Batch added {len(uris)} song(s)!")
                dialog.destroy()
            except requests.exceptions.RequestException as e:
                messagebox.showerror("Error", _parse_api_error(e))

        ttk.Button(btn_frame, text="Search All", command=do_search_all).pack(side="left", padx=5)
        btn_add_all = ttk.Button(btn_frame, text="Add All Matched", command=do_add_all, state="disabled")
        btn_add_all.pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

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
